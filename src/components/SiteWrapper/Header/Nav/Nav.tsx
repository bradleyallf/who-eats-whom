import { useState } from 'react'
import { Item } from './Item'

const routes = [
  // removing home link because of redundancy
  // {
  //   to: '/',
  //   label: 'Home',
  // },
  {
    to: '/about',
    label: 'About',
  },
  {
    to: '/how-to-submit',
    label: 'How to Submit',
  },
  {
    to: '/interactive-food-web',
    label: 'Interactive Food Web'
  }
]

export const  Nav = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  /* Makes the navigation responsive by toggling the menu on smaller screens */
  const [isOpen, setIsOpen] = useState(false)
  return (
    <nav className="relative w-full h-full">
      <div className="flex justify-end items-center md:hidden">
        <button
          type="button"
          aria-label="Toggle navigation menu"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((v) => !v)}
          className="rounded px-3 py-2 text-sm border border-slate-300"
        >
          ☰
        </button>
      </div>
  
      <div className="hidden md:flex w-full h-full flex-wrap gap-2 justify-end items-center">
        {routes.map((route, index) => (
          <Item key={index} {...route} />
        ))}
      </div>
  
      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 rounded-md border border-slate-200 bg-white p-2 shadow-md md:hidden z-50">
          <div className="flex flex-col gap-1">
            {routes.map((route, index) => (
              <button
                key={index}
                {...route}
                onClick={() => setIsOpen(false)}
                className="text-left"
              >
                <Item {...route} />
              </button>
            ))}
          </div>
        </div>
      )}
    </nav>
  )  
}
