import brandIcon96 from "./assets/brand-icon-96.png";
import brandIcon192 from "./assets/brand-icon-192.png";

export function BrandMark() {
  return (
    <div className="brand-mark" data-testid="brand-mark" aria-label="alphaloop">
      <img
        src={brandIcon96}
        srcSet={`${brandIcon96} 1x, ${brandIcon192} 2x`}
        width={96}
        height={96}
        alt=""
        aria-hidden
        decoding="async"
      />
    </div>
  );
}
