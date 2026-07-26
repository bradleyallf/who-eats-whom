export const getCurrentYear = () => new Date().getFullYear()

export const Footer = () => {
  const currentYear = getCurrentYear()
  const iNaturalistLogo = `${import.meta.env.BASE_URL}inaturalist-logo.png`

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <footer className="mt-12 bg-slate-200 px-4 py-8 text-xs text-slate-600">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-center gap-4 sm:flex-row sm:gap-6">
        <p>&copy; {currentYear} Bradley Allf</p>

        <a
          className="flex items-center gap-2 transition-opacity hover:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-200"
          href="https://www.inaturalist.org/"
          target="_blank"
          rel="noreferrer"
        >
          <span>Powered by</span>
          <img
            className="h-5 w-auto grayscale opacity-70"
            src={iNaturalistLogo}
            alt="iNaturalist"
          />
        </a>
      </div>
    </footer>
  )
}
