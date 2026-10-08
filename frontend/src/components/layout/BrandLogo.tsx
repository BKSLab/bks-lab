/* eslint-disable @next/next/no-img-element -- local SVG brand assets */
export function BrandLogo() {
  return (
    <>
      <img
        src="/brand/logo-horizontal-light.svg"
        alt=""
        aria-hidden="true"
        width={120}
        height={48}
        className="brand-logo-on-dark h-11 w-auto"
      />
      <img
        src="/brand/logo-horizontal-dark.svg"
        alt=""
        aria-hidden="true"
        width={120}
        height={48}
        className="brand-logo-on-light h-11 w-auto"
      />
    </>
  );
}
