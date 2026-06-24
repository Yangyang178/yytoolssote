export function chooseAndUploadFile(
  url: string,
  options: {
    count?: number
    type?: 'image' | 'video' | 'file'
    name?: string
    header?: Record<string, string>
    formData?: Record<string, any>
  } = {}
): Promise<any> {
  const { count = 1, type = 'file', name = 'file', header = {}, formData = {} } = options

  const token = uni.getStorageSync('yytools_token') as string
  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}
  const mergedHeader: Record<string, string> = { ...authHeader, ...header }

  return new Promise((resolve, reject) => {
    if (type === 'image') {
      uni.chooseImage({
        count,
        success: (res) => {
          const paths = Array.isArray(res.tempFilePaths) ? res.tempFilePaths : [res.tempFilePaths]
          const tasks = paths.map((filePath: string) =>
            uploadSingleFile(url, filePath, name, mergedHeader, formData)
          )
          Promise.all(tasks).then(resolve).catch(reject)
        },
        fail: reject,
      })
    } else if (type === 'video') {
      uni.chooseVideo({
        success: (res) => {
          uploadSingleFile(url, res.tempFilePath, name, mergedHeader, formData)
            .then(resolve)
            .catch(reject)
        },
        fail: reject,
      })
    } else {
      uni.chooseMessageFile({
        count,
        type: 'file',
        success: (res) => {
          const tasks = res.tempFiles.map((f: any) =>
            uploadSingleFile(url, f.path, name, mergedHeader, formData)
          )
          Promise.all(tasks).then(resolve).catch(reject)
        },
        fail: reject,
      })
    }
  })
}

function uploadSingleFile(
  url: string,
  filePath: string,
  name: string,
  header: Record<string, string>,
  formData: Record<string, any>
): Promise<any> {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url,
      filePath,
      name,
      header,
      formData,
      success: (res) => {
        if (res.statusCode === 200) {
          try {
            const data = JSON.parse(res.data as string)
            resolve(data)
          } catch {
            resolve(res.data)
          }
        } else {
          reject(new Error(`上传失败: ${res.statusCode}`))
        }
      },
      fail: reject,
    })
  })
}
