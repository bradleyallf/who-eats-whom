import { NavLink } from 'react-router-dom'

interface Props {
  to: string
  label: string
}

export const Item = (props: Props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { to, label } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <NavLink
      to={to}
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
