import type { RouteObject } from 'react-router-dom'

import { App } from './App/App'
import {
  About,
  HigherLevelChart,
  Home,
  HowToSubmit,
  NotFound,
  WhoSearch,
} from '@pages'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <Home />,
      },
      {
        path: 'about',
        element: <About />,
      },
      {
        path: 'how-to-submit',
        element: <HowToSubmit />,
      },
      {
        path: 'higher-level-chart',
        element: <HigherLevelChart />,
      },
      {
        path: 'who-search',
        element: <WhoSearch />,
      },
      {
        path: '*',
        element: <NotFound />,
      },
    ],
  },
]
// write a map function that removes "element" from each route object

export const routesSimple = routes.map((route) => {
  const { element, ...rest } = route
  return rest
})
