// Asset path utilities

/**
 * Prepend the base URL (e.g. /sandbox/) to an asset path.
 * This ensures assets load correctly regardless of whether the app is served from root or a subpath.
 */
export const getAssetPath = (path: string): string => {
    const base = import.meta.env.BASE_URL.endsWith('/')
        ? import.meta.env.BASE_URL.slice(0, -1)
        : import.meta.env.BASE_URL;

    const cleanPath = path.startsWith('/') ? path : `/${path}`;

    return `${base}${cleanPath}`;
};
