import { NavLink } from 'react-router-dom'

interface Props {
  to: string
  label: string
  onClick?: () => void
}

export const Item = (props: Props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { to, label, onClick } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive, isPending }) =>
        `hover:bg-slate-400 rounded px-2 py-1 text-sm ${
          isActive ? 'font-bold' : ''
        }`
      }
    >
      {label}
    </NavLink>
  )
}
