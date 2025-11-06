import { StrictMode } from 'react';
import * as ReactDOM from 'react-dom/client';
import {
  RouterProvider,
  createBrowserRouter,
} from 'react-router-dom';
import { routes } from './routes';
import 'leaflet/dist/leaflet.css';

const router = createBrowserRouter(routes, {
  basename: '/who-eats-whom',
});

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
