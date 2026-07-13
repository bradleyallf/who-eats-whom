import { StrictMode } from 'react';
import * as ReactDOM from 'react-dom/client';
import {
  RouterProvider,
  createBrowserRouter,
} from 'react-router-dom';
import { routes } from './routes';
import 'leaflet/dist/leaflet.css';

const baseName = import.meta.env.BASE_URL === '/'
  ? '/'
  : import.meta.env.BASE_URL.replace(/\/$/, '');

const router = createBrowserRouter(routes, {
  basename: baseName,
});

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
