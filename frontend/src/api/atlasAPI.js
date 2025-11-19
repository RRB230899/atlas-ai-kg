import axios from "axios";

const API_BASE = "http://127.0.0.1:8000";
const buildUrl = (path) => `${API_BASE}${path.startsWith("/") ? path : "/" + path}`;

const api = axios.create({
  baseURL: API_BASE,
  validateStatus: (status) => status >= 200 && status < 400,  // accept Chrome noise
});

api.interceptors.request.use((config) => {
  return config;
});

api.interceptors.response.use(
  (res) => {
    console.log("API OK:", res.status);
    return res;
  },
  (err) => {
    console.error("API ERROR:", err);
    return Promise.reject(err);
  }
);


// ---------------- API FUNCTIONS ---------------- //
export const ingestPDF = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const res = await api.post(buildUrl("/ingest"), formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return res.data;
};

export const search = async (query, k = 5) => {
  const res = await api.get(buildUrl("/search"), {
    params: { q: query, k }
  });
  return res.data;
};

export const searchWithEntities = async (query, k = 5) => {
  const res = await api.get(buildUrl("/search_with_entities"), {
    params: { q: query, k }
  });
  return res.data;
};

export const fetchSubgraph = async (entityName) => {
  const res = await api.get(buildUrl("/graph/entity"), {
    params: { name: entityName }
  });
  return res.data;
};
