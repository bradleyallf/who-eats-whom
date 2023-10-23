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
          Enter the common name of a species to see who it eats, or who eats it. For 
          example, try "Who is eaten by" "Osprey."
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
