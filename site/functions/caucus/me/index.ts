// Cloudflare Pages Function for /caucus/me: sends a signed-in caucus member to their own page.
//
// Cloudflare Access sits in front of /caucus/* and signs people in with a one-time code sent to their email
// (docs/auth.md). Access then adds a signed JWT to every request. This function checks that JWT, looks the
// email up in MEMBER_ACCOUNTS and redirects to that member's page. Anything it cannot resolve falls through to
// the static /caucus/me/ page, which explains what to do. Nothing here is needed for local dev or other hosts.
//
// Settings (Cloudflare Pages > Settings > Variables and secrets), none of them committed to the repo:
//   ACCESS_TEAM_DOMAIN  e.g. https://purple-nexus.cloudflareaccess.com
//   ACCESS_AUD          the Application Audience (AUD) tag of the Access application for /caucus
//   MEMBER_ACCOUNTS     secret, JSON mapping lower-case email to member slug, e.g. {"name@mail.house.gov": "jane-doe-ny"}

interface Env {
  ACCESS_TEAM_DOMAIN?: string;
  ACCESS_AUD?: string;
  MEMBER_ACCOUNTS?: string;
}

interface Context {
  request: Request;
  env: Env;
  next: () => Promise<Response>;
}

interface Jwk extends JsonWebKey {
  kid: string;
}

interface Claims {
  aud?: string | string[];
  iss?: string;
  exp?: number;
  nbf?: number;
  email?: string;
}

const b64url = (s: string) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
const json = <T>(part: string) => JSON.parse(new TextDecoder().decode(b64url(part))) as T;

let certs: { keys: Jwk[]; at: number } | undefined;

async function keysFor(team: string, refresh = false): Promise<Jwk[]> {
  if (!certs || refresh || Date.now() - certs.at > 3600_000) {
    const res = await fetch(`${team}/cdn-cgi/access/certs`);
    if (!res.ok) throw new Error(`Access certs: HTTP ${res.status}`);
    certs = { keys: ((await res.json()) as { keys: Jwk[] }).keys, at: Date.now() };
  }
  return certs.keys;
}

/** Returns the verified claims of an Access JWT, or null if it is missing, forged, expired or for another app. */
export async function verifyAccessJwt(token: string, team: string, aud: string, now = Date.now() / 1000): Promise<Claims | null> {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  const [h, p, s] = parts;
  const header = json<{ alg?: string; kid?: string }>(h);
  if (header.alg !== 'RS256' || !header.kid) return null;

  let jwk = (await keysFor(team)).find((k) => k.kid === header.kid);
  if (!jwk) jwk = (await keysFor(team, true)).find((k) => k.kid === header.kid);
  if (!jwk) return null;

  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  const ok = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, b64url(s), new TextEncoder().encode(`${h}.${p}`));
  if (!ok) return null;

  const claims = json<Claims>(p);
  const auds = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!auds.includes(aud)) return null;
  if (claims.iss !== team) return null;
  if (!claims.exp || claims.exp < now) return null;
  if (claims.nbf && claims.nbf > now + 60) return null;
  return claims;
}

export async function onRequestGet({ request, env, next }: Context): Promise<Response> {
  const team = env.ACCESS_TEAM_DOMAIN?.replace(/\/$/, '');
  const token = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!team || !env.ACCESS_AUD || !env.MEMBER_ACCOUNTS || !token) return next();

  const claims = await verifyAccessJwt(token, team, env.ACCESS_AUD).catch(() => null);
  if (!claims?.email) return next();

  const accounts = JSON.parse(env.MEMBER_ACCOUNTS) as Record<string, string>;
  const slug = accounts[claims.email.toLowerCase()];
  if (!slug || !/^[a-z0-9-]+$/.test(slug)) return next();

  return Response.redirect(new URL(`/caucus/members/${slug}/`, request.url).toString(), 302);
}
