import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'

const navItems = [
  {
    path: '/',
    icon: '🗺',
    label: 'Carte des prix',
    description: 'Heatmap & évolution',
  },
  {
    path: '/speculation',
    icon: '📈',
    label: 'Spéculation',
    description: 'Flips, acquisitions massives',
  },
  {
    path: '/gentrification',
    icon: '🏘',
    label: 'Gentrification',
    description: 'Risque de déplacement',
  },
  {
    path: '/ownership',
    icon: '🕸',
    label: 'Réseau propriétaires',
    description: 'Qui possède quoi',
  },
  {
    path: '/opportunities',
    icon: '🔑',
    label: 'Primo-accédants',
    description: 'Trouver son logement',
  },
  {
    path: '/transactions',
    icon: '📋',
    label: 'Transactions',
    description: 'Données DVF brutes',
  },
]

export function Sidebar() {
  return (
    <aside className="w-64 bg-surface-900 border-r border-surface-800 flex flex-col h-full">
      {/* Logo */}
      <div className="p-5 border-b border-surface-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary-600 rounded-lg flex items-center justify-center text-lg font-bold">
            P
          </div>
          <div>
            <h1 className="font-bold text-white text-sm leading-tight">PropriétéGraph</h1>
            <p className="text-xs text-slate-500 mt-0.5">Intelligence Immobilière</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-start gap-3 px-3 py-3 rounded-lg transition-colors group',
                isActive
                  ? 'bg-primary-600/20 text-primary-300'
                  : 'text-slate-400 hover:bg-surface-800 hover:text-slate-200'
              )
            }
          >
            <span className="text-xl mt-0.5 shrink-0">{item.icon}</span>
            <div className="min-w-0">
              <div className="text-sm font-medium">{item.label}</div>
              <div className="text-xs text-slate-500 mt-0.5">{item.description}</div>
            </div>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-surface-800">
        <div className="text-xs text-slate-600 space-y-1">
          <p className="font-medium text-slate-500">Sources</p>
          <a
            href="https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/"
            target="_blank"
            rel="noopener noreferrer"
            className="block hover:text-slate-400 transition-colors"
          >
            DVF — data.gouv.fr
          </a>
          <a
            href="https://adresse.data.gouv.fr/"
            target="_blank"
            rel="noopener noreferrer"
            className="block hover:text-slate-400 transition-colors"
          >
            Base Adresse Nationale
          </a>
          <a
            href="https://cadastre.data.gouv.fr/"
            target="_blank"
            rel="noopener noreferrer"
            className="block hover:text-slate-400 transition-colors"
          >
            Cadastre Etalab
          </a>
        </div>
      </div>
    </aside>
  )
}
