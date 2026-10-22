import axios from 'axios';
import publicApi from './api';
jest.mock('axios',()=>({get:jest.fn(),create:jest.fn(function(){return this;})}));
test.each([true,false,undefined,'true',1])('actual detail Axios config for flag %p',flag=>{
  window.__HTML_PILOT__=flag;
  const get=axios.get;
  get.mockClear(); publicApi.getPerson('a');publicApi.getArticle('b');
  const config=flag===true ? {params:{include_page_metadata:1}} : undefined;
  expect(get.mock.calls).toEqual(config ? [['/content/people/a',config],['/content/articles/b',config]] : [['/content/people/a'],['/content/articles/b']]);
  delete window.__HTML_PILOT__;
});
