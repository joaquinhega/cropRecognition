import { getJson } from "../api.js";

export const fetchTraining = (index) => getJson("/training", { index });

export const fetchTrainingPixels = () => getJson("/training/pixels");
