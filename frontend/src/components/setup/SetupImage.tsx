type SetupImageProps = {
  src: string;
  alt: string;
  caption?: string;
};

export default function SetupImage({ src, alt, caption }: SetupImageProps) {
  return (
    <figure className="overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[var(--bg-sidebar)]">
      <img
        src={src}
        alt={alt}
        className="block w-full"
        onError={(event) => {
          const img = event.currentTarget;
          img.style.display = "none";
          const placeholder = img.nextElementSibling;
          if (placeholder instanceof HTMLElement) {
            placeholder.style.display = "flex";
          }
        }}
      />
      <div
        className="hidden min-h-40 flex-col items-center justify-center gap-2 px-6 py-10 text-center"
        aria-hidden
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-gray-400 shadow-sm">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="h-6 w-6"
            aria-hidden
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z"
            />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-600">Screenshot coming soon</p>
        <p className="max-w-xs text-xs text-gray-400">{alt}</p>
      </div>
      {caption && (
        <figcaption className="border-t border-[var(--border-soft)] bg-white px-4 py-2 text-xs text-gray-500">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
