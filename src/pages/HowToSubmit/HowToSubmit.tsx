const basePath = import.meta.env.BASE_URL

export const HowToSubmit = () => {
  const headerImg = `${basePath}who_eats_whom_header.png`
  const projectsImg = `${basePath}Projects.png`
  const obsFieldImg = `${basePath}who_eats_whom_obs_field2.png`

  return (
    <section className="space-y-10 max-w-5xl mx-auto">
      <header className="space-y-3">
        <h1 className="text-4xl font-bold">How to Submit Observations</h1>
        <p className="text-lg text-slate-900">
          Anyone can contribute to Who Eats Whom—all you need is an iNaturalist account and a photo that clearly shows one organism feeding on another.
        </p>
        <p className="text-lg text-slate-900">
          Because feeding events typically involve <strong>two species</strong>, each event must be submitted to iNaturalist as <strong>two separate observations</strong>: one for the <strong>eater</strong> and one for the <strong>organism being eaten</strong>.
        </p>
        <p className="text-lg text-slate-900">
          Once both observations reach <em>Research Grade</em> and are properly linked, they will automatically appear in the Who Eats Whom database.
        </p>
      </header>

      <section className="space-y-3 border-t pt-6">
        <h2 className="text-3xl font-semibold">Step 1 — Create an iNaturalist account</h2>
        <p className="text-lg text-slate-900">
          If you’re new to iNaturalist, sign up at: <a href="https://www.inaturalist.org" className="text-cyan-700 underline" target="_blank" rel="noreferrer">https://www.inaturalist.org</a>
        </p>
        <p className="text-lg text-slate-900">Upload your photos as you normally would.</p>
      </section>

      <section className="space-y-4 border-t pt-6">
        <h2 className="text-3xl font-semibold">Step 2 — Join the Who Eats Whom project</h2>
        <p className="text-lg text-slate-900">
          Join the project by clicking “Join this project” here:{' '}
          <a
            href="https://www.inaturalist.org/projects/who-eats-whom"
            className="text-cyan-700 underline font-semibold"
            target="_blank"
            rel="noreferrer"
          >
            https://www.inaturalist.org/projects/who-eats-whom
          </a>
        </p>
        <p className="text-lg text-slate-900">You only need to join once.</p>
        <div className="w-full max-w-3xl rounded-md border border-slate-200 overflow-hidden shadow-sm">
          <img src={headerImg} alt="Join the Who Eats Whom project" className="w-full h-auto object-contain" loading="lazy" />
        </div>
      </section>

      <section className="space-y-4 border-t pt-6">
        <h2 className="text-3xl font-semibold">Step 3 — Create two observations</h2>
        <p className="text-lg text-slate-900">For a single feeding event, make two separate observations:</p>
        <ol className="list-decimal pl-6 space-y-1 text-lg text-slate-900">
          <li><strong>Observation A:</strong> the eater (predator, parasite, scavenger, pollinator, etc.)</li>
          <li><strong>Observation B:</strong> the organism being eaten (prey, host, carrion, nectar source, etc.)</li>
        </ol>
        <p className="text-lg text-slate-900">The image(s) in both observations should clearly document the interaction.</p>
      </section>

      <section className="space-y-4 border-t pt-6">
        <h2 className="text-3xl font-semibold">Step 4 — Add both observations to the project</h2>
        <p className="text-lg text-slate-900">On each observation page in iNaturalist:</p>
        <ol className="list-decimal pl-6 space-y-1 text-lg text-slate-900">
          <li>Scroll down to the <strong>Projects</strong> section.</li>
          <li>Add the observation to <strong>Who Eats Whom</strong>.</li>
        </ol>
        <p className="text-lg text-slate-900">Do this for both the “eater” and the “eatee.”</p>
        <div className="w-full max-w-lg rounded-md border border-slate-200 overflow-hidden shadow-sm">
          <img src={projectsImg} alt="Add observation to Who Eats Whom project" className="w-full h-auto object-contain" loading="lazy" />
        </div>
      </section>

      <section className="space-y-4 border-t pt-6">
        <h2 className="text-3xl font-semibold">Step 5 — Link the two observations</h2>
        <p className="text-lg text-slate-900">
          To ensure the interaction is recognized, the two observations must be linked in the <strong>Observation Fields</strong>. You will be
          automatically prompted to do this after you add an observation to Who Eats Whom.
        </p>
        <p className="text-lg text-slate-900">For both observations:</p>
        <ol className="list-decimal pl-6 space-y-1 text-lg text-slate-900">
          <li>Indicate which observation is for the “eater” and which is for the “organism being eaten”.</li>
          <li>Paste the URL to the observation’s “partner” in the feeding interaction.</li>
          <li>Indicate whether the observation is any of the special/unique types of feeding (parasitism, etc.).</li>
        </ol>
        <p className="text-lg text-slate-900">
          Filling out these observation fields allows our system to know the two records belong to the same event.
        </p>
        <div className="w-full max-w-3xl rounded-md border border-slate-200 overflow-hidden shadow-sm">
          <img src={obsFieldImg} alt="Observation fields linking example" className="w-full h-auto object-contain" loading="lazy" />
        </div>
      </section>

      <section className="space-y-3 border-t pt-6">
        <h2 className="text-3xl font-semibold">Step 6 — Reach Research Grade</h2>
        <p className="text-lg text-slate-900">
          Only interactions where <strong>both</strong> observations reach <strong>Research Grade</strong> will be added to the Who Eats Whom database.
        </p>
        <p className="text-lg text-slate-900">To reach Research Grade, an observation must meet iNaturalist’s standard criteria:</p>
        <ul className="list-disc pl-6 space-y-1 text-lg text-slate-900">
          <li>a date</li>
          <li>a location</li>
          <li>a photo</li>
          <li>a wild organism</li>
          <li>a community-supported taxonomic ID agreed on by two or more users</li>
        </ul>
        <p className="text-lg text-slate-900">
          Note that this is the same data quality standard used by other sites that ingest iNaturalist data, such as GBIF. Tip: clearer photos
          and correct linking help other identifiers quickly verify the record.
        </p>
      </section>

      <section className="space-y-3 border-t pt-6">
        <h2 className="text-3xl font-semibold">What kinds of interactions can I submit?</h2>
        <p className="text-lg text-slate-900">Who Eats Whom accepts a wide range of feeding relationships, including:</p>
        <ul className="list-disc pl-6 space-y-1 text-lg text-slate-900">
          <li>Predation</li>
          <li>Herbivory</li>
          <li>Scavenging</li>
          <li>Parasitism</li>
          <li>Pollination</li>
          <li>Nectar feeding</li>
          <li>In short, any instance where one organism is obtaining food from another</li>
        </ul>
      </section>

      <section className="space-y-3 border-t pt-6">
        <h2 className="text-3xl font-semibold">What not to submit</h2>
        <ul className="list-disc pl-6 space-y-1 text-lg text-slate-900">
          <li>Interactions <strong>without visible evidence</strong> of feeding</li>
          <li>Observations without a way to identify each organism</li>
          <li>Captive or staged feeding events (iNaturalist rules discourage these)</li>
        </ul>
      </section>

      <section className="space-y-3 border-t pt-6">
        <h2 className="text-3xl font-semibold">After you submit</h2>
        <p className="text-lg text-slate-900">If both observations become Research Grade and are correctly linked:</p>
        <ul className="list-disc pl-6 space-y-1 text-lg text-slate-900">
          <li>The interaction is automatically ingested by Who Eats Whom</li>
          <li>Your observation appears in our database, map, graph view, and interactive global food web</li>
          <li>You help build the first global, photographic record of trophic interactions</li>
        </ul>
      </section>
    </section>
  )
}
