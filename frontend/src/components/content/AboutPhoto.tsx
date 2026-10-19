import Image from "next/image";

interface AboutPhotoProps {
  src: string;
  alt: string;
  width: number;
  height: number;
  sizes: string;
  caption?: string;
  eager?: boolean;
  className?: string;
}

export function AboutPhoto({
  src,
  alt,
  width,
  height,
  sizes,
  caption,
  eager = false,
  className = "",
}: AboutPhotoProps) {
  return (
    <figure className={`m-0 min-w-0 ${className}`}>
      <Image
        src={src}
        alt={alt}
        width={width}
        height={height}
        sizes={sizes}
        loading={eager ? "eager" : "lazy"}
        className="block h-auto w-full rounded-card"
      />
      {caption && (
        <figcaption className="mt-3 text-sm leading-relaxed text-text-muted">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
