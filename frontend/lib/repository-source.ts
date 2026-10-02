export type RepositorySource = { type: 'local'; path: string } | { type: 'github'; url: string; ref?: string };
export type AnalysisIntent = { mode: 'PROACTIVE' | 'ON_DEMAND'; request_text?: string };
export type RepositorySubmission = { source: RepositorySource; intent: AnalysisIntent; autoDiscover: boolean };
export function sourceBody(source: RepositorySource | string) {
  return typeof source === 'string' ? { repository_path: source } : { source };
}
export function validGitHubURL(value: string): boolean {
  try {
    const u=new URL(value);
    const match=/^\/([A-Za-z0-9][A-Za-z0-9-]{0,38})\/([A-Za-z0-9_.-]{1,100})\/?$/.exec(u.pathname);
    return u.protocol==='https:' && u.host==='github.com' && !u.username && !u.password && !u.search && !u.hash && !/[?#\s]/.test(value) && !!match &&
      !match[1].includes('--') && !match[1].endsWith('-') && !['','.','..'].includes(match[2].replace(/\.git$/,''));
  } catch { return false; }
}
