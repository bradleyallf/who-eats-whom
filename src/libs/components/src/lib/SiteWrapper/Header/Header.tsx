import { Nav } from './Nav/Nav'

export const Header = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <header>
      <section className="w-full bg-slate-100 flex justify-between p-4">
        <div className="">
          <h1 className="font-bold text-lg">Who Eats Whom</h1>
          <h2 className="text-sm">A planetary food web</h2>
        </div>
        <div className="basis-1/2 grow">
          <Nav />
        </div>
      </section>
    </header>
  )
}
