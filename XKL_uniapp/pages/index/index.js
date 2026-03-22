import {ref} from 'vue'

export const index = () => {
    const title = ref('欢迎来到XKL')
    return {
        title
    }
}