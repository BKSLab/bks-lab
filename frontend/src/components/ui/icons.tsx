// Shared inline SVG icon set (design spec section 18). No icon library is
// loaded; every icon is decorative by default (aria-hidden), standalone
// icon buttons get their accessible name from the wrapping element.

interface IconProps {
  className?: string;
}

function BaseIcon({
  className,
  children,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      className={className}
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

export function SearchIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </BaseIcon>
  );
}

export function MenuIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="17" x2="20" y2="17" />
    </BaseIcon>
  );
}

export function CloseIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <line x1="6" y1="6" x2="18" y2="18" />
      <line x1="18" y1="6" x2="6" y2="18" />
    </BaseIcon>
  );
}

export function ArrowRightIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </BaseIcon>
  );
}

export function SunIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <circle cx="12" cy="12" r="4" />
      <line x1="12" y1="2" x2="12" y2="4" />
      <line x1="12" y1="20" x2="12" y2="22" />
      <line x1="4.93" y1="4.93" x2="6.34" y2="6.34" />
      <line x1="17.66" y1="17.66" x2="19.07" y2="19.07" />
      <line x1="2" y1="12" x2="4" y2="12" />
      <line x1="20" y1="12" x2="22" y2="12" />
      <line x1="4.93" y1="19.07" x2="6.34" y2="17.66" />
      <line x1="17.66" y1="6.34" x2="19.07" y2="4.93" />
    </BaseIcon>
  );
}

export function MoonIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </BaseIcon>
  );
}

export function CodeIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </BaseIcon>
  );
}

export function ManagementIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="9" y1="4" x2="9" y2="20" />
      <line x1="15" y1="4" x2="15" y2="20" />
    </BaseIcon>
  );
}

export function AiIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <rect x="5" y="5" width="14" height="14" rx="2" />
      <rect x="10" y="10" width="4" height="4" />
      <line x1="9" y1="2" x2="9" y2="5" />
      <line x1="15" y1="2" x2="15" y2="5" />
      <line x1="9" y1="19" x2="9" y2="22" />
      <line x1="15" y1="19" x2="15" y2="22" />
      <line x1="2" y1="9" x2="5" y2="9" />
      <line x1="2" y1="15" x2="5" y2="15" />
      <line x1="19" y1="9" x2="22" y2="9" />
      <line x1="19" y1="15" x2="22" y2="15" />
    </BaseIcon>
  );
}

export function AccessibilityIcon({ className }: IconProps) {
  return (
    <BaseIcon className={className}>
      <circle cx="12" cy="5" r="2" />
      <path d="M4 9h16" />
      <path d="M12 9v5" />
      <path d="M12 14l-3 7" />
      <path d="M12 14l3 7" />
    </BaseIcon>
  );
}
