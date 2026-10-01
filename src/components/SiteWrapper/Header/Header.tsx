import { Nav } from './Nav/Nav'
import { Link } from 'react-router-dom'

export const Header = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <header className="sticky top-0 z-50">
      <section className="w-full bg-slate-100 flex justify-between p-4">
        <div>
          <Link to="/" className="no-underline text-inherit">
            <h1 className="font-bold text-lg">Who Eats Whom</h1>
            <h2 className="text-sm">A planetary food web</h2>
          </Link>
        </div>
        <div className="basis-1/2 grow">
          <Nav />
        </div>
      </section>
    </header>
  )
}
