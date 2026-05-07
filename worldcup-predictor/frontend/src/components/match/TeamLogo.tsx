import { cn } from '@/lib/utils';

interface TeamLogoProps {
  src?: string | null;
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZE_PX: Record<NonNullable<TeamLogoProps['size']>, number> = {
  sm: 24,
  md: 36,
  lg: 56,
};

/**
 * Team crest with a fallback monogram when the logo URL is missing or
 * fails to load. Uses native <img> (not next/image) because team logos
 * come from many third-party CDNs we haven't allow-listed in
 * next.config.mjs — and because these are tiny files that don't benefit
 * from the build-time optimisation pipeline.
 */
export function TeamLogo({ src, name, size = 'md', className }: TeamLogoProps) {
  const px = SIZE_PX[size];
  const initials = name
    ?.replace(/[\s·]+/g, ' ')
    .trim()
    .slice(0, 2)
    .toUpperCase();
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-slate-700/60 bg-slate-900/80 text-slate-300',
        className,
      )}
      style={{ width: px, height: px, fontSize: Math.round(px * 0.38) }}
      aria-hidden="true"
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          width={px}
          height={px}
          className="h-full w-full object-contain"
          onError={(e) => {
            // Hide the broken image so the monogram shows through.
            (e.currentTarget as HTMLImageElement).style.display = 'none';
          }}
        />
      ) : (
        <span className="font-semibold tabular-nums">{initials}</span>
      )}
    </span>
  );
}
