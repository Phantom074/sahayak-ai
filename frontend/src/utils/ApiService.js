import axios from 'axios';

class ApiService {
  constructor() {
    // Base URL for the backend API
    // In development, this will proxy to http://localhost:8000 via the proxy setting in package.json
    // In production, this would be the actual backend URL
    this.apiClient = axios.create({
      baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/v1',
      timeout: 30000, // 30 seconds timeout
      headers: {
        'Content-Type': 'application/json',
      }
    });

    // Add request interceptor to include auth token if available
    this.apiClient.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('sahayak_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Add response interceptor to handle errors globally
    this.apiClient.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error);
        return Promise.reject(error);
      }
    );
  }

  // Conversation API methods
  async sendMessage(text, language = 'hi', sessionId = null) {
    try {
      const response = await this.apiClient.post('/conversation/process', {
        text,
        language,
        channel: 'web',
        session_id: sessionId
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async startNewSession(userData = {}) {
    try {
      const response = await this.apiClient.post('/conversation/start', {
        language_preference: userData.language || 'hi',
        channel: 'web',
        ...userData
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // Voice API methods
  async transcribeAudio(audioBlob, language = 'hi') {
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.wav');
      formData.append('language_hint', language);
      formData.append('channel', 'web');

      const response = await this.apiClient.post('/stt/transcribe', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async synthesizeText(text, language = 'hi', sessionId = null) {
    try {
      const response = await this.apiClient.post('/tts/synthesize', {
        text,
        language,
        session_id: sessionId || 'default'
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // Scheme retrieval API methods
  async searchSchemes(query, filters = {}) {
    try {
      const response = await this.apiClient.post('/retrieval/search', {
        query,
        filters,
        language: filters.language || 'hi'
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getSchemesByCategory(category, language = 'hi') {
    try {
      const response = await this.apiClient.get(`/retrieval/category/${category}`, {
        params: { language }
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // Eligibility API methods
  async checkEligibility(schemeId, userProfile) {
    try {
      const response = await this.apiClient.post('/eligibility/check', {
        scheme_id: schemeId,
        user_profile: userProfile
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getSchemeRules(schemeId) {
    try {
      const response = await this.apiClient.get(`/eligibility/rules/${schemeId}`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // User profile API methods
  async createUserProfile(profileData) {
    try {
      const response = await this.apiClient.post('/profile/create', profileData);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getUserProfile(profileId) {
    try {
      const response = await this.apiClient.get(`/profile/${profileId}`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async updateUserProfile(profileId, profileData) {
    try {
      const response = await this.apiClient.put(`/profile/${profileId}`, profileData);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getConsentStatus(profileId) {
    try {
      const response = await this.apiClient.get(`/profile/${profileId}/consent`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async updateConsent(profileId, consentData) {
    try {
      const response = await this.apiClient.post(`/profile/${profileId}/consent`, consentData);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // Utility methods
  async getSupportedLanguages() {
    try {
      const response = await this.apiClient.get('/languages');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getSupportedChannels() {
    try {
      const response = await this.apiClient.get('/channels');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async healthCheck() {
    try {
      const response = await this.apiClient.get('/health');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // Error handling helper
  handleError(error) {
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      const message = error.response.data?.message || error.response.statusText;
      
      switch (status) {
        case 400:
          return new Error(`Bad Request: ${message}`);
        case 401:
          return new Error('Unauthorized: Please log in again');
        case 403:
          return new Error('Forbidden: Insufficient permissions');
        case 404:
          return new Error('Not Found: The requested resource does not exist');
        case 500:
          return new Error(`Server Error: ${message}`);
        default:
          return new Error(`HTTP Error: ${status} - ${message}`);
      }
    } else if (error.request) {
      // Request was made but no response received
      return new Error('Network Error: Unable to reach the server. Please check your connection.');
    } else {
      // Something else happened
      return new Error(`Request Error: ${error.message}`);
    }
  }
}

export default new ApiService();