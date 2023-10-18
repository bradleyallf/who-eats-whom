import { Web } from '@components'

export const Home = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <div className="col-12 text-center">
        <h1 className="text-xl font-bold">Who Eats Whom</h1>
        <h2 className="text-sm">
          Enter the name of a plant, animal or fungus to see what it eats.
        </h2>
        <a
          href="https://www.inaturalist.org/projects/who-eats-whom"
          className="text-xs text-cyan-700 underline"
        >
          See the project on iNaturalist
        </a>
      </div>
      <Web />
    </>
  )
}
