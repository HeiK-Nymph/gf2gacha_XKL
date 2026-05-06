const BASE_URL = 'http://localhost:8080' //Java 服务器地址
const TIMEOUT = 20000 //默认超时时间

const getHeader = (contentType = 'application/json') => {
    const header = {
        'Content-Type': contentType,
        // 'Authorization': uni.getStorageSync('token') || ''
    }
    return header
}

function request(options) {
    const {
        url,
        method = 'GET',
        data,
        params,
        loading = false,
        loadingText = '加载中...',
        timeout = TIMEOUT,
        showError = true
    } = options

    if (loading) {
        uni.showLoading({
            title: loadingText,
            mask: true
        })
    }

    let fullUrl = BASE_URL + url
    if (params) {
        const queryStr = Object.keys(params)
            .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
            .join('&')
        fullUrl += (fullUrl.includes('?') ? '&' : '?') + queryStr
    }

    const requestData = method.toUpperCase() === 'GET' ? null : data

    return new Promise((resolve, reject) => {
        uni.request({
            url: fullUrl,
            method: method.toUpperCase(),
            data: requestData,
            header: getHeader(),
            timeout,
            success: (res) => {
                // ===== 响应拦截器 =====
                const { statusCode, data: responseData } = res

                // HTTP 层面失败
                if (statusCode !== 200) {
                    _handleHttpError(statusCode, showError)
                    reject({ code: statusCode, msg: 'HTTP 错误' })
                    return
                }

                // 业务层面：你的后端返回 Result<T> 格式
                // { code: 200, msg: "success", data: ... }
                const result = responseData
                if (result.code === 200 || result.code === 0) { // 成功
                    resolve(result.data)   // 直接解包，业务层拿到的是纯 data
                } else {
                    // 业务错误码
                    if (showError) {
                        uni.showToast({
                            title: result.msg || '请求失败',
                            icon: 'none',
                            duration: 2000
                        })
                    }
                    reject(result)
                }
            },
            fail: (err) => {
                // 网络层错误（无网、超时、DNS 失败等）
                if (showError) {
                    uni.showToast({
                        title: '网络异常',
                        icon: 'none',
                        duration: 2000
                    })
                }
                reject(err)
            },
            complete: () => {
                if (loading) {
                    uni.hideLoading()
                }
            }

        })
    })
}

// =============================================
// 4. 快捷方法
// =============================================

function get(url, params, options = {}) {
    return request({ url, method: 'GET', params, ...options })
}

function post(url, data, options = {}) {
    return request({ url, method: 'POST', data, ...options })
}

function put(url, data, options = {}) {
    return request({ url, method: 'PUT', data, ...options })
}

function del(url, data, options = {}) {
    return request({ url, method: 'DELETE', data, ...options })
}

// =============================================
// 5. 内部错误处理
// =============================================

function _handleHttpError(statusCode, showError) {
    const errorMap = {
        401: '登录已过期，请重新登录',
        403: '没有权限访问',
        404: '请求的资源不存在',
        500: '服务器内部错误',
        502: '网关错误',
        503: '服务不可用'
    }
    const msg = errorMap[statusCode] || `请求失败(${statusCode})`
    
    if (showError) {
        uni.showToast({ title: msg, icon: 'none', duration: 2000 })
    }

    // 401 自动跳转登录页（如果有的话）
    if (statusCode === 401) {
        // uni.reLaunch({ url: '/pages/login/login' })
        console.warn('[AUTH] Token 过期，需要重新登录')
    }
}

// =============================================
// 6. 导出
// =============================================

export default { request, get, post, put, del }