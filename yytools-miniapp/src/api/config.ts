const BASE_URL = 'http://localhost:9876'

export const config = {
  baseUrl: BASE_URL,
  apiPrefix: '/miniapp/api',
  tokenKey: 'yytools_token',
  userInfoKey: 'yytools_user_info',
}

export function getFullUrl(path: string): string {
  return `${config.baseUrl}${config.apiPrefix}${path}`
}
