import React from 'react';
import loadable from '@loadable/component';

import { routePaths } from '$route/routePaths';

import Main from '$components/layouts/Main';

const fallback = <p>Loading...</p>;
const LoadableHome = loadable(() => import('$screens/HomeScreen'), { fallback });
const LoadableNotFound = loadable(() => import('$screens/NotFoundScreen'), { fallback });

export const routes = [
  {
    path: routePaths.home,
    element: <Main />,
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
