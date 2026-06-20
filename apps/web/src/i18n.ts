import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import { enUS } from "./locales/en-US";

export const resources = {
  "en-US": {
    translation: enUS,
  },
} as const;

if (!i18next.isInitialized) {
  void i18next.use(initReactI18next).init({
    resources,
    lng: "en-US",
    fallbackLng: "en-US",
    interpolation: {
      escapeValue: false,
    },
  });
}

export { i18next };
