import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useGachaRecordStore = defineStore('gachaRecord', () => {
    const gacha = ref({
  "permanent_pool": [],
  "character_pool": [],
  "weapon_pool": []
})

    const characterGacha = computed(() => {
        return gacha.value.character_pool
    })

    const weaponGacha = computed(() => {
        return gacha.value.weapon_pool
    })

    const permanentGacha = computed(() => {
        return gacha.value.permanent_pool
    })

    return { gacha, characterGacha, weaponGacha, permanentGacha }
})