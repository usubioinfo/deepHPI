const rawBaseUrl = import.meta.env.BASE_URL || "/";

function normalizeBasePath(value) {
  if (!value || value === "/") {
    return "";
  }

  const trimmed = value.endsWith("/") ? value.slice(0, -1) : value;
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

export const BASE_PATH = normalizeBasePath(rawBaseUrl);

export function stripBasePath(pathname) {
  if (!BASE_PATH) {
    return pathname || "/";
  }

  if (!pathname) {
    return "/";
  }

  if (pathname === BASE_PATH) {
    return "/";
  }

  if (pathname.startsWith(`${BASE_PATH}/`)) {
    return pathname.slice(BASE_PATH.length) || "/";
  }

  return pathname;
}

export function withBasePath(pathname) {
  if (!pathname) {
    return BASE_PATH || "/";
  }

  const normalized = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${BASE_PATH}${normalized}` || "/";
}

export function assetPath(pathname) {
  return withBasePath(pathname);
}
