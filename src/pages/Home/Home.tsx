import { Web } from '../../components'

export const Home = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <div className="col-12 mx-auto max-w-3xl text-center">
        <h1 className="text-4xl font-bold">Who Eats Whom</h1>
        <h2 className="mt-1 text-sm leading-snug sm:mt-2">
          Enter the name of a species to see who it eats, or who eats it.
          For example, try "Who is eaten by" "Osprey."
        </h2>
        <a
          href="https://www.inaturalist.org/projects/who-eats-whom"
          className="mt-1 inline-block text-xs text-cyan-700 underline sm:mt-2"
        >
          See the project on iNaturalist
        </a>
      </div>
      <Web />
    </>
  )
}
