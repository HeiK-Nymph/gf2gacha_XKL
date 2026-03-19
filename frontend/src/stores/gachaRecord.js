import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useGachaRecordStore = defineStore('gachaRecord', () => {
    const gacha = ref({
  "permanent_pool": [  ],
  "character_pool": [],
  "weapon_pool": [],
  "custom_character_pool": [],
  "custom_weapon_pool": [],
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

    const customCharacterGacha = computed(() => {
        return gacha.value.custom_character_pool
    })

    const customWeaponGacha = computed(() => {
        return gacha.value.custom_weapon_pool
    })

    return { gacha, characterGacha, weaponGacha, permanentGacha, customCharacterGacha, customWeaponGacha }
})