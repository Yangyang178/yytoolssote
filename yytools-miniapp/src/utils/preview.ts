export function previewFile(url: string, fileName: string) {
  const ext = fileName.split('.').pop()?.toLowerCase() || ''

  const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico']
  const videoExts = ['mp4', 'webm', 'ogg', 'm4v']
  const docExts = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']

  if (imageExts.includes(ext)) {
    uni.previewImage({
      urls: [url],
      current: url,
    })
  } else if (videoExts.includes(ext)) {
    uni.previewMedia({
      sources: [{ url, type: 'video' }],
      current: 0,
    })
  } else if (docExts.includes(ext)) {
    uni.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode === 200) {
          uni.openDocument({
            filePath: res.tempFilePath,
            showMenu: true,
          })
        }
      },
      fail: () => {
        uni.showToast({ title: '文件预览失败', icon: 'none' })
      },
    })
  } else {
    uni.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode === 200) {
          uni.openDocument({
            filePath: res.tempFilePath,
            showMenu: true,
          })
        }
      },
      fail: () => {
        uni.showToast({ title: '不支持预览此文件类型', icon: 'none' })
      },
    })
  }
}

export function downloadFile(url: string, fileName: string) {
  uni.downloadFile({
    url,
    success: (res) => {
      if (res.statusCode === 200) {
        uni.saveFile({
          tempFilePath: res.tempFilePath,
          success: () => {
            uni.showToast({ title: '文件已保存', icon: 'success' })
          },
        })
      }
    },
    fail: () => {
      uni.showToast({ title: '下载失败', icon: 'none' })
    },
  })
}
