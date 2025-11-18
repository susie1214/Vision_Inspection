import axios from "axios";
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://localhost:8000"
});

// images
export const listImages = () => api.get("/api/images").then(r=>r.data);

// annotations
export const getAnns = (image_id) =>
  api.get("/api/annotations", { params:{ image_id }}).then(r=>r.data);

export const saveAnns = (anns) =>
  api.post("/api/annotations", anns).then(r=>r.data);
