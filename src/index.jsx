import promise from 'es6-promise';
import 'isomorphic-fetch';
import '$scss/global.scss'; // Must stay above App import

import React from 'react';
import { render } from 'react-dom';
import { BrowserRouter } from 'react-router-dom';

import App from './App';

promise.polyfill();

render((
  <BrowserRouter>
    <App />
  </BrowserRouter>
), document.getElementById('root'));
