import React from 'react';
import loadable from '@loadable/component';

import { routePaths } from '$route/routePaths';

import Layout from '$components/general/Layout';

const fallback = <p>Loading...</p>;
const LoadableHome = loadable(() => import('$screens/HomeScreen'), { fallback });
const LoadableNotFound = loadable(() => import('$screens/NotFoundScreen'), { fallback });

// const defaultConfig = {
//   path: null,
//   component: null,
//   exact: true,
//   redirect: () => false, // We might not ever need a redirect
//   subPaths: null,
// };
//
// export const routeConfig = [
//   {
//     ...defaultConfig,
//     path: routePaths.home,
//     component: LoadableHome,
//   },
//   {
//     ...defaultConfig,
//     path: routePaths.about,
//     component: LoadableHome, // TODO
//   },
// ];

export const routes = [
  {
    path: routePaths.home,
    element: <Layout />,
    children: [
      { index: true, element: <LoadableHome /> },
      {
        path: routePaths.about,
        element: <LoadableHome />,
      },
      { path: '*', element: <LoadableNotFound /> },
    ],
  },
];
