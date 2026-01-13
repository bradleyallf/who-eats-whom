import { Item } from './Item'

const routes = [
  {
    to: '/',
    label: 'Home',
  },
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

export const Nav = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <nav className="w-full h-full flex flex-wrap gap-2 justify-end items-center">
      {routes.map((route, index) => (
        <Item key={index} {...route} />
      ))}
    </nav>
  )
}
