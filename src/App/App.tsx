import { SiteWrapper } from '@components'
import { Outlet } from 'react-router'

export const App = () => {
  return (
    <SiteWrapper>
      <main id="mainContent" className="min-h-screen">
        <Outlet />
      </main>
    </SiteWrapper>
  )
}
