const basePath = import.meta.env.BASE_URL

const team = [
  {
    name: 'Dr. Bradley Allf',
    role: 'Founder',
    bio: 'Postdoctoral researcher in ecology, citizen science, and biodiversity.',
    img: `${basePath}bradley_headshot.jpg`,
  },
  {
    name: 'Dr. Aditi Mallavarapu',
    role: 'Technical Lead',
    bio: 'Computer scientist specializing in networks, data-driven design, and interactive systems.',
    img: `${basePath}Aditi.png`,
  },
  {
    name: 'Nikhil Vasudeva',
    role: 'Developer',
    bio: 'Undergraduate researcher contributing to development, data pipelines, and interactive tools.',
    img: `${basePath}nvasude4@ncsu.edu-4443ec62.jpg`,
  },
  {
    name: 'Adam Biscoe',
    role: 'Developer',
    bio: 'Undergraduate researcher concentrating on front-end development and improving user experience.',
    img: `${basePath}Adam.jpg`,
  },

  {
    name: 'Maithili Bhoop',
    role: 'Front-End Developer',
    bio: 'Undergraduate researcher focused on interface design, accessibility, and improving user experience.',
    img: `${basePath}Maithili-Bhoop.jpg`,
  },
]

export const About = () => {
  return (
    <section className="space-y-12 max-w-5xl mx-auto">
      <header className="space-y-3">
        <h1 className="text-4xl font-bold">About Who Eats Whom</h1>
        <p className="text-lg italic text-slate-800">
          “When we try to pick out anything by itself, we find it hitched to
          everything else in the universe.”
          <span className="ml-1 not-italic">– John Muir</span>
        </p>
      </header>

      <article className="space-y-10 text-slate-900 leading-relaxed">
        <section className="space-y-3">
          <h2 className="text-3xl font-semibold">Our Mission</h2>
          <p className="text-lg">
            Who Eats Whom exists to showcase the deep interconnectedness of life
            on Earth. Our goal is to build a centralized, searchable repository
            of species’ feeding relationships—each one linked to a verifiable
            photograph of the interaction. By bringing these records together in
            one place, we aim to make it easy for anyone—from scientists to the
            general public—to learn what species eat, and to explore the web of
            interactions that together make up the global ecological system.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-3xl font-semibold">Why We Built This</h2>
          <p className="text-lg">
            For much of the history of ecology, confirmed feeding interactions
            have been scattered across small natural history notes buried in
            taxon-specific journals. These records are invaluable, but difficult
            to discover. Many never make it to the people who could benefit from
            them—students, naturalists, teachers, land managers, ecologists, and
            anyone simply curious about the world outside their window.
          </p>
          <p className="text-lg">
            Who Eats Whom was created to solve this problem. Instead of digging
            through decades of natural history literature, users can now search,
            explore, and visualize feeding interactions supported by clear
            photographic evidence contributed by the global iNaturalist
            community.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-3xl font-semibold">What’s in the Database</h2>
          <p className="text-lg">
            All records on Who Eats Whom come from iNaturalist observations that
            show a feeding interaction. To appear on the site:
          </p>
          <ol className="list-decimal pl-6 space-y-2 text-lg">
            <li>
              A user must first join the{' '}
              <a
                href="https://www.inaturalist.org/projects/who-eats-whom"
                className="text-cyan-700 underline font-semibold"
                target="_blank"
                rel="noreferrer"
              >
                Who Eats Whom project
              </a>{' '}
              on iNaturalist.
            </li>
            <li>
              Users then add separate observations for the{' '}
              <strong>“eater”</strong> and the{' '}
              <strong>organism being eaten.</strong>
            </li>
            <li className="space-y-1">
              Users then link the two observations in the “observation fields”
              section by adding the partner observation’s URL.
            </li>
            <li>
              When both observations reach <strong>Research Grade</strong>, they
              are automatically sent to the Who Eats Whom database.
            </li>
          </ol>
          <p className="text-lg">
            We include a wide range of interactions in our definition of
            feeding—including predation, scavenging, parasitism, and
            pollination—and future versions of the site will allow users to
            filter by interaction type.
          </p>
          <p className="text-lg">
            As of late 2025, the database includes{' '}
            <strong>~13,000 verified feeding records</strong> from around the
            world, each tied to a real photograph.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-3xl font-semibold">How the Data Are Created</h2>
          <p className="text-lg">
            Records come entirely from the iNaturalist community. No computer
            vision or automated detection is used—every observation is manually
            added by project members who either photographed the event
            themselves or noticed that someone else’s upload captured a feeding
            interaction.
          </p>
          <p className="text-lg">
            This combination of community participation and manual review helps
            maintain high data quality and ensures that every record is real,
            specific, and verifiable.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-3xl font-semibold">
            Tools for Exploring the Web of Life
          </h2>
          <p className="text-lg">
            Who Eats Whom offers multiple ways to explore species interactions:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-lg">
            <li>
              <strong>Grid View:</strong> View photos of the feeding
              interaction, and follow links to the observations on iNaturalist
            </li>
            <li>
              <strong>Graph View:</strong> Explore what a species eats,
              organized by broad groups (mammals, insects, plants, etc.).
            </li>
            <li>
              <strong>Network View:</strong> Visualize the network of organisms
              connected by feeding relationships.
            </li>
            <li>
              <strong>Map View:</strong> See how feeding interactions vary
              across geography.
            </li>
            <li>
              <strong>Interactive Global Food Web Tool:</strong> Manipulate and
              zoom through the global network of feeding relationships, seeing
              how species are linked across ecosystems and continents.
            </li>
          </ul>
          <p className="text-lg">
            Our long-term vision is to make Who Eats Whom a one-stop resource
            for anyone—from casual naturalists to research scientists—
            interested in discovering, exploring, or analyzing trophic
            interactions.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-3xl font-semibold">How It Started</h2>
          <p className="text-lg">
            The seed of Who Eats Whom was planted in the summer of 2014. As an
            undergraduate field assistant studying snake mimicry in eastern
            North Carolina, <strong>Bradley Allf</strong> heard a friend (Chris
            Akcali) describe seeing a Southeastern Five-lined Skink eat a wood
            cockroach earlier that season. Curious whether this interaction had
            ever been formally documented, Chris searched through old issues of{' '}
            <em>Herpetological Review</em> and found that it had not—so he
            decided to publish the observation as a natural history note.
          </p>
          <p className="text-lg">
            Bradley remembered thinking that there should be a centralized place
            for these kinds of records—somewhere more accessible than scattered
            natural history notes, and somewhere that could grow continuously as
            new interactions were observed.
          </p>
          <p className="text-lg">
            He carried the idea into graduate school, eventually building a
            small mockup for an R programming class and later releasing a
            <a
              href="https://forum.inaturalist.org/t/who-eats-whom-a-new-site-for-searching-inaturalist-feeding-interactions/46218/3"
              className="text-cyan-700 underline"
              target="_blank"
              rel="noreferrer"
            >
              {' '}
              rudimentary first version
            </a>
            . The idea survived, evolved, and expanded.
          </p>
          <p className="text-lg">
            In 2025, while a postdoc at North Carolina State University, Bradley
            connected with computer scientist <strong>Aditi Mallavarapu</strong>
            , who shared enthusiasm for the project and brought expertise in
            networks, databases, and software development. With her student{' '}
            <strong>Nikhil Vasudeva</strong>, they rebuilt the site and launched
            the much improved version 2.0 of Who Eats Whom in late 2025.
          </p>
        </section>
      </article>

      <section className="space-y-6">
        <h2 className="text-3xl font-semibold">Our Team</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {team.map((member) => (
            <div
              key={member.name}
              className="flex flex-col items-center gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="w-full overflow-hidden rounded-md border border-slate-200">
                <img
                  src={member.img}
                  alt={member.name}
                  className="w-full h-auto object-contain"
                  loading="lazy"
                />
              </div>
              <div className="text-center space-y-1">
                <p className="text-lg font-semibold text-slate-900">
                  {member.name}{' '}
                  <span className="font-normal">– {member.role}</span>
                </p>
                <p className="text-base text-slate-700">{member.bio}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="text-sm text-slate-700">
          We are so grateful to the iNaturalist community and staff, whose
          shared observations and digital infrastructure, respectively, make
          this project possible (note that Who Eats Whom is not formally
          affiliated with iNaturalist in any way).
        </p>
      </section>
      <section className="space-y-10">
        <div className="space-y-3">
          <h2 className="text-3xl font-semibold">Cite Our Data</h2>
          <p className="text-sm font-semibold text-slate-700">
            If you use this data, please cite our paper:
          </p>
          <p className="text-sm text-slate-700">
            Mallavarapu, A., Uzzo, S., Vasudeva, N., Dunn, R., Allf, B., “Who
            Eats Whom: Modeling trophic interaction networks with large-scale,
            crowdsourced ecological data”. In: Proceedings of The Fourteenth
            International Conference on Complex Networks and their Applications:
            COMPLEX NETWORKS 2025. Ed. by H. Cherifi, L. M. Rocha, C. Cherifi,
            and Z. Ertem. Springer. Dec. 2025.
          </p>
        </div>
      </section>
    </section>
  )
}
