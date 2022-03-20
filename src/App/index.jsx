import React from 'react';
import {
  useRoutes,
} from 'react-router-dom';

import { routes } from '$route/routeConfig';

const App = () => {
  const app = useRoutes(routes);
  return (
    <>
      { app }
    </>
  );
};

export default App;
