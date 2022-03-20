import React from 'react';
import loadable from '@loadable/component';

import { routePaths } from '$route/routePaths';

import Main from '$components/layouts/Main';

const fallback = <p>Loading...</p>;
const LoadableHome = loadable(() => import('$screens/HomeScreen'), { fallback });
const LoadableAbout = loadable(() => import('$screens/About'), { fallback });
const LoadableHowToSubmit = loadable(() => import('$screens/HowToSubmit'), { fallback });
const LoadableHigherLevelChart = loadable(() => import('$screens/HigherLevelChart'), { fallback });
const LoadableNotFound = loadable(() => import('$screens/NotFoundScreen'), { fallback });

export const routes = [
  {
    path: routePaths.home,
    element: <Main />,
    children: [
      { index: true, element: <LoadableHome /> },
      {
        path: routePaths.about,
        element: <LoadableAbout />,
      },
      {
        path: routePaths.howToSubmit,
        element: <LoadableHowToSubmit />,
      },
      {
        path: routePaths.higherLevelChart,
        element: <LoadableHigherLevelChart />,
      },
      { path: '*', element: <LoadableNotFound /> },
    ],
  },
];
