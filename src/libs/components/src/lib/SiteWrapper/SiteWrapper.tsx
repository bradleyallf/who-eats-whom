import { Header } from './Header/Header'
import { Footer } from './Footer/Footer'
import { ReactNode } from 'react'

interface Props {
  children: ReactNode
}

export const SiteWrapper = (props: Props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { children } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <Header />
      <div className="px-4 md:px-8 mt-12">{children}</div>
      <Footer />
    </>
  )
}
