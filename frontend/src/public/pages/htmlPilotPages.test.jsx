import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter, Routes, Route, useNavigate} from 'react-router-dom';
import Person from './PersonDetailPage';
import Article from './ArticleDetailPage';
import api from '../utils/api';
import {useHtmlPilotNavigation} from '../utils/htmlPilot';
jest.mock('../utils/api', () => ({__esModule:true, default:{getPerson:jest.fn(),getArticle:jest.fn(),getPersonCareer:jest.fn(),getPersonShows:jest.fn()}}));
jest.mock('../components/RatingCard', () => () => null);
jest.mock('../components/RelatedArticles', () => () => null);
jest.mock('../components/RelatedNews', () => () => null);
jest.mock('date-fns/locale', () => ({ru:{}}));
let root, navigate;
const deferred = () => { let resolve,reject; const promise=new Promise((r,j)=>{resolve=r;reject=j;});return {promise,resolve,reject}; };
function Harness({kind, Page}) { navigate=useNavigate();useHtmlPilotNavigation(); return <Routes><Route path={'/'+kind+'/:slug'} element={<Page/>}/><Route path="/other" element={<p>Other</p>}/></Routes>; }
beforeEach(() => {
  window.__HTML_PILOT__=true;
  document.head.innerHTML='<title>Сервер SEO</title><link rel="canonical" href="https://humorpedia.ru/people/a">';
  document.body.innerHTML='<div id="html-pilot-fallback" data-path="/people/a">Серверный текст</div><div id="root" hidden></div>';
  root=createRoot(document.getElementById('root'));
  api.getPersonCareer.mockResolvedValue({data:{teams:[],roles:[]}}); api.getPersonShows.mockResolvedValue({data:{items:[]}});
});
afterEach(async()=>{await act(async()=>root.unmount());delete window.__HTML_PILOT__;});
const data = title => ({title,slug:title,_id:title,modules:[],page_metadata:{title:'SEO '+title,canonical_url:'https://humorpedia.ru/people/'+title,robots:'noindex,follow'}});
describe.each([['people',Person,'getPerson'],['articles',Article,'getArticle']])('%s pilot page', (kind,Page,method) => {
  const mount=async()=>{document.getElementById('html-pilot-fallback').dataset.path='/'+kind+'/a';await act(async()=>root.render(<MemoryRouter initialEntries={['/'+kind+'/a']}><Harness kind={kind} Page={Page}/></MemoryRouter>));};
  test('single GET, SEO survives loading and becomes ready only with current response',async()=>{
    const request=deferred();api[method].mockReturnValue(request.promise);await mount();
    expect(document.title).toBe('Сервер SEO'); expect(document.getElementById('root').hidden).toBe(true);
    await act(async()=>request.resolve({data:data('a')}));
    expect(api[method]).toHaveBeenCalledTimes(1);expect(document.title).toBe('SEO a');
    expect(document.getElementById('root').hidden).toBe(false);expect(document.querySelectorAll('h1')).toHaveLength(1);
  });
  test('A B A ignores old requests and previous loaded state',async()=>{
    const a=deferred(), b=deferred(), latest=deferred();api[method].mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise).mockReturnValueOnce(latest.promise);await mount();
    await act(async()=>navigate('/'+kind+'/b'));await act(async()=>navigate('/'+kind+'/a'));
    await act(async()=>b.resolve({data:data('b')}));await act(async()=>a.resolve({data:data('stale')}));
    expect(document.title).toBe('Сервер SEO');expect(document.querySelector('h1')).toBeNull();
    await act(async()=>latest.resolve({data:data('latest')}));expect(document.title).toBe('SEO latest');
    expect(document.querySelector('h1').textContent).toContain('latest');
    await act(async()=>navigate('/other'));expect(document.querySelector('link[rel="canonical"]')).toBeNull();
  });
  test('Back to previously loaded key waits for the new request generation',async()=>{
    const first=deferred(), b=deferred(), second=deferred();api[method].mockReturnValueOnce(first.promise).mockReturnValueOnce(b.promise).mockReturnValueOnce(second.promise);await mount();
    await act(async()=>first.resolve({data:data('first')}));
    await act(async()=>navigate('/'+kind+'/b'));
    document.title='В ожидании свежего ответа';
    await act(async()=>navigate(-1));
    expect(document.title).toBe('В ожидании свежего ответа');expect(document.querySelector('h1')).toBeNull();
    await act(async()=>second.resolve({data:data('fresh')}));expect(document.title).toBe('SEO fresh');
    await act(async()=>b.resolve({data:data('stale-b')}));expect(document.title).toBe('SEO fresh');
  });
  test.each([404,500])('failure %i has correct fallback semantics',async status=>{
    const request=deferred();api[method].mockReturnValue(request.promise);await mount();
    await act(async()=>request.reject({response:{status}}));
    if(status===404){expect(document.getElementById('html-pilot-fallback')).toBeNull();expect(document.getElementById('root').hidden).toBe(false);expect(document.querySelector('meta[name="robots"]').content).toBe('noindex,follow');}
    else{expect(document.getElementById('html-pilot-fallback')).not.toBeNull();expect(document.title).toBe('Сервер SEO');expect(document.querySelector('[role="status"]')).not.toBeNull();}
  });
  test('disabled flag preserves old title flow',async()=>{window.__HTML_PILOT__=false;api[method].mockResolvedValue({data:data('legacy')});await mount();expect(document.title).toBe('legacy | humorpedia.ru');});
});
