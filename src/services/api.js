import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SANA_URL, SANA_API_KEY } from '../config';

// Preset servers. "tunnel" (ngrok) is the default so the app works from
// anywhere without Tailscale. The Tailscale presets are kept as fallbacks for
// when you're on the same private network.
export const SERVERS = {
  tunnel: {
    id: 'tunnel',
    name: 'Tunnel',
    label: 'Anywhere',
    url: SANA_URL,
    description: 'Reach the Mac from anywhere (ngrok)',
  },
  mac: {
    id: 'mac',
    name: 'MacBook',
    label: 'Smart Brain',
    url: 'http://100.115.8.84:8000',
    description: 'Qwen 14B, same Tailscale network',
  },
  jetson: {
    id: 'jetson',
    name: 'Jetson',
    label: 'Always On',
    url: 'http://100.72.202.14:8000',
    description: 'Low power, Tailscale network',
  },
};

const USER_ID = 'krishna';
const DEFAULT_SERVER_ID = 'tunnel';

const getActiveServer = async () => {
  const customUrl = await AsyncStorage.getItem('sana_custom_url');
  if (customUrl) return customUrl;
  const serverId = (await AsyncStorage.getItem('sana_server_id')) || DEFAULT_SERVER_ID;
  return SERVERS[serverId] ? SERVERS[serverId].url : SERVERS[DEFAULT_SERVER_ID].url;
};

// API key: AsyncStorage override wins, otherwise the baked-in config value.
export const getApiKey = async () => {
  const stored = await AsyncStorage.getItem('sana_api_key');
  return stored || SANA_API_KEY;
};

export const setApiKey = async (key) => {
  await AsyncStorage.setItem('sana_api_key', key);
};

const authHeaders = async (extra = {}) => {
  const key = await getApiKey();
  return { ...extra, 'X-SANA-Key': key };
};

const api = async () => {
  const baseURL = await getActiveServer();
  const headers = await authHeaders({ 'Content-Type': 'application/json' });
  return axios.create({ baseURL, timeout: 60000, headers });
};

export const sendMessage = async (message) => {
  const conversationId = await AsyncStorage.getItem('conversation_id');
  const client = await api();
  const response = await client.post('/chat/', {
    message,
    user_id: USER_ID,
    conversation_id: conversationId || null,
  });
  if (response.data.conversation_id) {
    await AsyncStorage.setItem('conversation_id', response.data.conversation_id);
  }
  return response.data;
};

export const checkHealth = async (serverUrl) => {
  try {
    const baseURL = serverUrl || (await getActiveServer());
    const headers = await authHeaders();
    const client = axios.create({ baseURL, timeout: 5000, headers });
    const response = await client.get('/health/');
    return response.data;
  } catch (error) {
    return { status: 'offline', error: error.message };
  }
};

export const checkOllama = async (serverUrl) => {
  try {
    const baseURL = serverUrl || (await getActiveServer());
    const headers = await authHeaders();
    const client = axios.create({ baseURL, timeout: 5000, headers });
    const response = await client.get('/health/ollama');
    return response.data;
  } catch (error) {
    return { status: 'offline', error: error.message };
  }
};

export const newConversation = async () => {
  await AsyncStorage.removeItem('conversation_id');
};

export const getConversations = async () => {
  try {
    const client = await api();
    const response = await client.get('/chat/history/' + USER_ID);
    return response.data;
  } catch (error) {
    console.log('[SANA] getConversations error:', error.message);
    return [];
  }
};

export const loadConversation = async (conversationId) => {
  const client = await api();
  const response = await client.get('/chat/history/' + USER_ID + '/' + conversationId);
  await AsyncStorage.setItem('conversation_id', conversationId);
  return response.data;
};

export const deleteConversation = async (conversationId) => {
  const client = await api();
  const response = await client.delete('/chat/history/' + USER_ID + '/' + conversationId);
  const activeId = await AsyncStorage.getItem('conversation_id');
  if (activeId === conversationId) {
    await AsyncStorage.removeItem('conversation_id');
  }
  return response.data;
};

export const deleteAllConversations = async () => {
  const client = await api();
  const response = await client.delete('/chat/history/' + USER_ID);
  await AsyncStorage.removeItem('conversation_id');
  return response.data;
};

export const getCurrentServerId = async () => {
  const custom = await AsyncStorage.getItem('sana_custom_url');
  if (custom) return 'custom';
  return (await AsyncStorage.getItem('sana_server_id')) || DEFAULT_SERVER_ID;
};

export const setServer = async (serverId) => {
  await AsyncStorage.removeItem('sana_custom_url');
  await AsyncStorage.setItem('sana_server_id', serverId);
  await AsyncStorage.removeItem('conversation_id');
};

export const setCustomUrl = async (url) => {
  await AsyncStorage.setItem('sana_custom_url', url);
  await AsyncStorage.removeItem('conversation_id');
};

export const clearCustomUrl = async () => {
  await AsyncStorage.removeItem('sana_custom_url');
};

export const getCustomUrl = async () => {
  return (await AsyncStorage.getItem('sana_custom_url')) || '';
};
