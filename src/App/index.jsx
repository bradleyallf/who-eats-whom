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
  // return (
  //   <Router>
  //     <div>
  //       <Switch>
  //         {
  //           routeConfig.map((route) => (
  //             <RouteWithSubPaths
  //               key={`route${route.path}`}
  //               {...route} // eslint-disable-line react/jsx-props-no-spreading
  //             />
  //           ))
  //         }
  //         <Redirect from="/index.html" to="/" />
  //         <Route component={NotFoundScreen} />
  //       </Switch>
  //     </div>
  //   </Router>
  // );
};

export default App;
