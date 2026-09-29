"""Sequential BFS strategy reuse with a deterministic crawler boundary."""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import types

import pytest

BASE=Path(__file__).parent/os.environ.get('VARIANT','after')
for name,path in [('crawl4ai','crawl4ai'),('crawl4ai.deep_crawling','crawl4ai/deep_crawling')]:
    package=types.ModuleType(name)
    package.__path__=[str(BASE/path)]
    sys.modules[name]=package
models=types.ModuleType('crawl4ai.models')
class Stats:
    def __init__(self,**kwargs):
        self.__dict__.update(kwargs)
        self.urls_skipped=0
models.TraversalStats=Stats
sys.modules[models.__name__]=models
kinds=types.ModuleType('crawl4ai.types')
for name in ['AsyncWebCrawler','CrawlerRunConfig','CrawlResult','RunManyReturn']:
    setattr(kinds,name,object)
sys.modules[kinds.__name__]=kinds
utils=types.ModuleType('crawl4ai.utils')
utils.HeadPeekr=object
# max_depth=0: neither normalization helper nor network filters is invoked.
def unused(*args,**kwargs):
    raise AssertionError('Unexpected URL normalization in root-only test')
utils.normalize_url_for_deep_crawl=unused
utils.efficient_normalize_url_for_deep_crawl=unused
sys.modules[utils.__name__]=utils

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,BASE/path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

base=load('crawl4ai.deep_crawling.base_strategy','crawl4ai/deep_crawling/base_strategy.py')
sys.modules['crawl4ai.deep_crawling'].DeepCrawlStrategy=base.DeepCrawlStrategy
load('crawl4ai.deep_crawling.filters','crawl4ai/deep_crawling/filters.py')
load('crawl4ai.deep_crawling.scorers','crawl4ai/deep_crawling/scorers.py')
BFS=load('crawl4ai.deep_crawling.bfs_strategy','crawl4ai/deep_crawling/bfs_strategy.py').BFSDeepCrawlStrategy

class Config:
    def __init__(self,stream=False): self.stream=stream
    def clone(self,**kwargs): return Config(kwargs.get('stream',self.stream))
class Crawler:
    async def arun_many(self,urls,config):
        items=[types.SimpleNamespace(url=url,success=True,metadata=None,links={'internal':[]}) for url in urls]
        if not config.stream: return items
        async def stream():
            for item in items: yield item
        return stream()

async def run(strategy,url,stream):
    result=await strategy.arun(start_url=url,crawler=Crawler(),config=Config(stream))
    return [item async for item in result] if stream else result

@pytest.mark.parametrize('modes',[(False,False),(False,True),(True,False),(True,True)])
@pytest.mark.parametrize('limit',[2,3])
def test_sequential_fresh_runs_keep_separate_budget(modes,limit):
    async def check():
        strategy=BFS(max_depth=0,max_pages=limit)
        for i in range(5):
            stream=modes[i%2]
            url=f'https://example.test/page-{i}'
            got=await run(strategy,url,stream)
            expected=await run(BFS(max_depth=0,max_pages=limit),url,stream)
            assert [r.url for r in got]==[r.url for r in expected]==[url]
            assert strategy._pages_crawled==1
    asyncio.run(check())

@pytest.mark.parametrize('stream',[False,True])
def test_resume_preserves_saved_count(stream):
    async def check():
        state={'visited':[], 'pending':[{'url':'https://example.test/resumed','parent_url':None}],
               'depths':{'https://example.test/resumed':0},'pages_crawled':4}
        strategy=BFS(max_depth=0,max_pages=10,resume_state=state)
        got=await run(strategy,'https://unused.test/',stream)
        assert len(got)==1
        assert strategy._pages_crawled==5
    asyncio.run(check())

@pytest.mark.parametrize('stream',[False,True])
def test_cancel_then_start_fresh_has_new_budget(stream):
    async def check():
        strategy=BFS(max_depth=0,max_pages=2)
        await run(strategy,'https://example.test/first',stream)
        strategy.cancel()
        got=await run(strategy,'https://example.test/second',stream)
        assert not strategy.cancelled
        assert [r.url for r in got]==['https://example.test/second']
        assert strategy._pages_crawled==1
    asyncio.run(check())
