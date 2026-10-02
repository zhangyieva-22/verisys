// Presentation copy only; HTTP codes and all server-owned result semantics are unchanged.
const messages: Record<string,string> = {
  INVALID_REPOSITORY_SOURCE: 'Enter a public GitHub repository URL and a valid analysis request.',
  REPOSITORY_NOT_FOUND_OR_PRIVATE: 'Verisys could not access this public repository. Check the URL and make sure it is public.',
  PRIVATE_REPOSITORY_UNSUPPORTED: 'Private repositories are not supported. Choose a public GitHub repository.',
  INVALID_REPOSITORY_REF: 'That branch, tag or commit could not be resolved. Check the ref and try again.',
  GITHUB_RATE_LIMIT: 'GitHub is limiting repository requests. Try again later.',
  REMOTE_TIMEOUT: 'The GitHub repository request timed out. Try again.',
  REPOSITORY_TOO_LARGE: 'This repository exceeds the supported intake limits. Try a smaller repository.',
  MALFORMED_ARCHIVE: 'Verisys could not read this repository archive safely.',
  UNSAFE_ARCHIVE_CONTENT: 'The repository archive contains unsupported or unsafe entries.',
  ANALYSIS_STALE: 'The repository snapshot changed. Analyze it again before continuing.',
  DISCOVERY_PROVIDER_FAILED: 'Verification discovery is temporarily unavailable. Try again later.',
};
export function apiErrorMessage(code: unknown, fallback: string): string {
  return typeof code === 'string' ? messages[code] ?? fallback : fallback;
}
