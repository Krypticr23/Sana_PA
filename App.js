import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  StatusBar,
  SafeAreaView,
  Alert,
  Modal,
  Pressable,
} from 'react-native';
import {
  sendMessage,
  newConversation,
  getConversations,
  loadConversation,
  deleteConversation,
  deleteAllConversations,
  checkHealth,
  getCurrentServerId,
  setServer,
  setCustomUrl,
  clearCustomUrl,
  getCustomUrl,
  SERVERS,
} from './src/services/api';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);

  const [currentServerId, setCurrentServerId] = useState('jetson');
  const [customUrlInput, setCustomUrlInput] = useState('');
  const [serverStatuses, setServerStatuses] = useState({});

  const scrollRef = useRef(null);

  useEffect(() => {
    initServer();
  }, []);

  const initServer = async () => {
    try {
      const sid = await getCurrentServerId();
      setCurrentServerId(sid);
      const custom = await getCustomUrl();
      setCustomUrlInput(custom);
    } catch (e) {
      console.log('[SANA] initServer error:', e.message);
    }
  };

  const refreshConversations = async () => {
    try {
      const convos = await getConversations();
      setConversations(Array.isArray(convos) ? convos : []);
    } catch (e) {
      console.log('[SANA] refreshConversations error:', e.message);
      setConversations([]);
    }
  };

  // ---- Drawer ----
  const openDrawer = () => {
    console.log('[SANA] openDrawer tapped');
    setDrawerOpen(true);
    refreshConversations();
  };

  const closeDrawer = () => {
    console.log('[SANA] closeDrawer tapped');
    setDrawerOpen(false);
  };

  // ---- Chat ----
  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);
    try {
      const data = await sendMessage(userMessage);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response }]);
      if (!activeConversationId && data.conversation_id) {
        setActiveConversationId(data.conversation_id);
      }
    } catch (error) {
      console.log('[SANA] send error:', error.message);
      Alert.alert('Connection error', 'Could not reach SANA. Check the server in Settings.');
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Connection failed. Try another server.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = async () => {
    console.log('[SANA] new chat tapped');
    try {
      await newConversation();
    } catch (e) {
      console.log('[SANA] newConversation error:', e.message);
    }
    setMessages([]);
    setActiveConversationId(null);
    setDrawerOpen(false);
  };

  const handleLoadConversation = async (convId) => {
    console.log('[SANA] load conversation tapped:', convId);
    try {
      const history = await loadConversation(convId);
      const formatted = (history || []).map((m) => ({ role: m.role, content: m.content }));
      setMessages(formatted);
      setActiveConversationId(convId);
      setDrawerOpen(false);
    } catch (e) {
      Alert.alert('Error', 'Failed to load conversation');
    }
  };

  const handleDeleteConversation = (convId, preview) => {
    console.log('[SANA] delete conversation tapped:', convId);
    Alert.alert('Delete conversation?', '"' + (preview || 'Conversation') + '" will be permanently deleted.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteConversation(convId);
            if (activeConversationId === convId) {
              setMessages([]);
              setActiveConversationId(null);
            }
            await refreshConversations();
          } catch (e) {
            Alert.alert('Error', 'Failed to delete conversation');
          }
        },
      },
    ]);
  };

  const handleDeleteAll = () => {
    Alert.alert('Delete all conversations?', 'This permanently deletes all chat history. This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete All',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteAllConversations();
            setMessages([]);
            setActiveConversationId(null);
            setConversations([]);
            Alert.alert('Done', 'All conversations deleted.');
          } catch (e) {
            Alert.alert('Error', 'Failed to delete conversations');
          }
        },
      },
    ]);
  };

  // ---- Settings ----
  const openSettings = () => {
    console.log('[SANA] settings tapped');
    // Close drawer first; iOS cannot reliably show two modals at once.
    setDrawerOpen(false);
    setTimeout(() => {
      setSettingsOpen(true);
      checkAllServers();
    }, 350);
  };

  const checkAllServers = async () => {
    setServerStatuses({});
    const statuses = {};
    const entries = Object.entries(SERVERS);
    for (let i = 0; i < entries.length; i++) {
      const id = entries[i][0];
      const server = entries[i][1];
      const result = await checkHealth(server.url);
      statuses[id] = result.status;
    }
    setServerStatuses(statuses);
  };

  const handleSelectServer = async (serverId) => {
    console.log('[SANA] select server tapped:', serverId);
    try {
      await setServer(serverId);
      setCurrentServerId(serverId);
      setMessages([]);
      setActiveConversationId(null);
      Alert.alert('Switched', 'Now using ' + SERVERS[serverId].name);
    } catch (e) {
      Alert.alert('Error', 'Failed to switch server');
    }
  };

  const handleSaveCustomUrl = async () => {
    if (!customUrlInput.trim()) {
      Alert.alert('Empty URL', 'Custom URL cannot be empty');
      return;
    }
    try {
      await setCustomUrl(customUrlInput.trim());
      setCurrentServerId('custom');
      setMessages([]);
      setActiveConversationId(null);
      Alert.alert('Saved', 'Using custom server URL');
    } catch (e) {
      Alert.alert('Error', 'Failed to save URL');
    }
  };

  const handleClearCustomUrl = async () => {
    try {
      await clearCustomUrl();
      setCustomUrlInput('');
      setCurrentServerId('jetson');
      Alert.alert('Cleared', 'Reverted to Jetson server');
    } catch (e) {
      Alert.alert('Error', 'Failed to clear URL');
    }
  };

  useEffect(() => {
    const t = setTimeout(() => {
      if (scrollRef.current) scrollRef.current.scrollToEnd({ animated: true });
    }, 100);
    return () => clearTimeout(t);
  }, [messages, loading]);

  const showEmptyState = messages.length === 0;

  const statusColor = (s) => {
    if (s === 'online') return '#22c55e';
    if (s === 'offline') return '#ef4444';
    return '#666';
  };

  const activeServer =
    currentServerId === 'custom'
      ? { name: 'Custom', label: 'User defined' }
      : SERVERS[currentServerId] || SERVERS.jetson;

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#000" />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={openDrawer} style={styles.menuBtn} activeOpacity={0.6} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
          <View style={styles.menuLine} />
          <View style={[styles.menuLine, { width: 14 }]} />
          <View style={styles.menuLine} />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <View style={styles.statusDot} />
          <Text style={styles.headerTitle}>SANA</Text>
          <Text style={styles.serverBadge}>{'· ' + activeServer.name}</Text>
        </View>
        <TouchableOpacity onPress={handleNewChat} style={styles.newChatBtn} activeOpacity={0.6} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
          <Text style={styles.newChatText}>+</Text>
        </TouchableOpacity>
      </View>

      {/* Chat area */}
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        {showEmptyState ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>Good to see you</Text>
            <Text style={styles.emptySubtitle}>What can I help you with today?</Text>
            <View style={styles.suggestions}>
              {['Plan my day', 'Help me prep for a meeting', 'Remind me to call mom tonight', 'Summarize my week'].map((s, i) => (
                <TouchableOpacity key={i} style={styles.suggestionChip} onPress={() => setInput(s)} activeOpacity={0.6}>
                  <Text style={styles.suggestionText}>{s}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        ) : (
          <ScrollView ref={scrollRef} style={styles.flex} contentContainerStyle={styles.messagesContent} showsVerticalScrollIndicator={false}>
            {messages.map((msg, idx) => (
              <View key={idx} style={[styles.messageRow, msg.role === 'user' ? styles.userRow : styles.assistantRow]}>
                {msg.role === 'assistant' && (
                  <View style={styles.avatar}>
                    <Text style={styles.avatarText}>S</Text>
                  </View>
                )}
                <View style={[styles.bubble, msg.role === 'user' ? styles.userBubble : styles.assistantBubble]}>
                  <Text style={msg.role === 'user' ? styles.userText : styles.assistantText}>{msg.content}</Text>
                </View>
              </View>
            ))}
            {loading && (
              <View style={[styles.messageRow, styles.assistantRow]}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>S</Text>
                </View>
                <View style={[styles.bubble, styles.assistantBubble]}>
                  <Text style={styles.assistantText}>Thinking...</Text>
                </View>
              </View>
            )}
          </ScrollView>
        )}

        {/* Input */}
        <View style={styles.inputWrapper}>
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.input}
              value={input}
              onChangeText={setInput}
              placeholder="Message SANA"
              placeholderTextColor="#5a5a5a"
              multiline
              maxLength={1000}
            />
            <TouchableOpacity
              onPress={handleSend}
              style={[styles.sendBtn, (!input.trim() || loading) && styles.sendBtnDisabled]}
              disabled={!input.trim() || loading}
              activeOpacity={0.6}
            >
              <Text style={styles.sendArrow}>↑</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>

      {/* ===== Drawer (Modal-based: always receives touches) ===== */}
      <Modal visible={drawerOpen} transparent animationType="fade" onRequestClose={closeDrawer}>
        <View style={styles.drawerRoot}>
          <SafeAreaView style={styles.drawerPanel}>
            <View style={styles.drawerHeader}>
              <Text style={styles.drawerLogo}>SANA</Text>
              <TouchableOpacity onPress={closeDrawer} style={styles.closeBtn} activeOpacity={0.6} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                <Text style={styles.closeText}>X</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.newChatRow} onPress={handleNewChat} activeOpacity={0.6}>
              <View style={styles.newChatIcon}>
                <Text style={styles.newChatIconText}>+</Text>
              </View>
              <Text style={styles.newChatRowText}>New chat</Text>
            </TouchableOpacity>

            <Text style={styles.sectionLabel}>Recent</Text>
            <ScrollView style={styles.conversationsList} showsVerticalScrollIndicator={false}>
              {conversations.length === 0 ? (
                <Text style={styles.emptyConvos}>No conversations yet</Text>
              ) : (
                conversations.map((c) => (
                  <View key={c.id} style={[styles.conversationItem, activeConversationId === c.id && styles.activeConversation]}>
                    <TouchableOpacity style={styles.conversationMain} onPress={() => handleLoadConversation(c.id)} activeOpacity={0.6}>
                      <Text style={styles.conversationPreview} numberOfLines={1}>
                        {c.preview}
                      </Text>
                      <Text style={styles.conversationDate}>{new Date(c.created_at).toLocaleDateString()}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.deleteBtn}
                      onPress={() => handleDeleteConversation(c.id, c.preview)}
                      activeOpacity={0.5}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    >
                      <Text style={styles.deleteBtnText}>x</Text>
                    </TouchableOpacity>
                  </View>
                ))
              )}
            </ScrollView>

            <View style={styles.drawerFooter}>
              <TouchableOpacity style={styles.footerRow} activeOpacity={0.6} onPress={openSettings}>
                <View style={styles.userAvatar}>
                  <Text style={styles.userAvatarText}>K</Text>
                </View>
                <View style={styles.userInfo}>
                  <Text style={styles.userName}>Krishna</Text>
                  <Text style={styles.userStatus}>{activeServer.name + ' · Private mode'}</Text>
                </View>
                <Text style={styles.settingsIcon}>⚙</Text>
              </TouchableOpacity>
            </View>
          </SafeAreaView>

          {/* Tap empty area to close */}
          <Pressable style={styles.drawerDismiss} onPress={closeDrawer} />
        </View>
      </Modal>

      {/* ===== Settings Modal ===== */}
      <Modal visible={settingsOpen} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setSettingsOpen(false)}>
        <SafeAreaView style={styles.settingsContainer}>
          <View style={styles.settingsHeader}>
            <Text style={styles.settingsTitle}>Settings</Text>
            <TouchableOpacity onPress={() => setSettingsOpen(false)} style={styles.closeBtn} activeOpacity={0.6} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Text style={styles.closeText}>X</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.settingsContent} showsVerticalScrollIndicator={false}>
            <Text style={styles.settingsSection}>Server</Text>

            {Object.values(SERVERS).map((server) => {
              const isActive = currentServerId === server.id;
              const status = serverStatuses[server.id];
              return (
                <TouchableOpacity
                  key={server.id}
                  style={[styles.serverCard, isActive && styles.serverCardActive]}
                  onPress={() => handleSelectServer(server.id)}
                  activeOpacity={0.7}
                >
                  <View style={styles.serverCardHeader}>
                    <View style={styles.flex}>
                      <View style={styles.serverNameRow}>
                        <Text style={styles.serverName}>{server.name}</Text>
                        <View style={[styles.serverStatusDot, { backgroundColor: statusColor(status) }]} />
                      </View>
                      <Text style={styles.serverLabel}>{server.label}</Text>
                      <Text style={styles.serverDesc}>{server.description}</Text>
                    </View>
                    {isActive && (
                      <View style={styles.activeBadge}>
                        <Text style={styles.activeBadgeText}>ACTIVE</Text>
                      </View>
                    )}
                  </View>
                  <Text style={styles.serverUrl}>{server.url}</Text>
                </TouchableOpacity>
              );
            })}

            <Text style={styles.settingsSection}>Custom Server</Text>
            <View style={styles.settingsCard}>
              <Text style={styles.settingsLabel}>Override with custom URL</Text>
              <TextInput
                style={styles.settingsInput}
                value={customUrlInput}
                onChangeText={setCustomUrlInput}
                placeholder="http://100.x.x.x:8000"
                placeholderTextColor="#555"
                autoCapitalize="none"
                autoCorrect={false}
              />
              <View style={styles.btnRow}>
                <TouchableOpacity style={[styles.saveBtn, styles.btnHalfLeft]} onPress={handleSaveCustomUrl} activeOpacity={0.7}>
                  <Text style={styles.saveBtnText}>Use Custom</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.clearBtn, styles.btnHalf]} onPress={handleClearCustomUrl} activeOpacity={0.7}>
                  <Text style={styles.clearBtnText}>Clear</Text>
                </TouchableOpacity>
              </View>
            </View>

            <Text style={styles.settingsSection}>Account</Text>
            <View style={styles.settingsCard}>
              <View style={styles.accountRow}>
                <View style={styles.userAvatarLarge}>
                  <Text style={styles.userAvatarLargeText}>K</Text>
                </View>
                <View style={styles.flex}>
                  <Text style={styles.accountName}>Krishna</Text>
                  <Text style={styles.accountSub}>Private mode · Local only</Text>
                </View>
              </View>
            </View>

            <Text style={styles.settingsSection}>Danger Zone</Text>
            <View style={styles.settingsCard}>
              <TouchableOpacity style={styles.dangerBtn} onPress={handleDeleteAll} activeOpacity={0.7}>
                <Text style={styles.dangerBtnText}>Delete All Conversations</Text>
              </TouchableOpacity>
              <Text style={styles.dangerHint}>This permanently removes all chat history on the current server.</Text>
            </View>

            <Text style={styles.settingsSection}>About</Text>
            <View style={styles.settingsCard}>
              <View style={styles.aboutRow}>
                <Text style={styles.settingsLabel}>Version</Text>
                <Text style={styles.aboutValue}>0.2.1</Text>
              </View>
              <View style={styles.divider} />
              <View style={styles.aboutRow}>
                <Text style={styles.settingsLabel}>Active server</Text>
                <Text style={styles.aboutValue}>{activeServer.name}</Text>
              </View>
            </View>

            <View style={styles.bottomSpacer} />
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  flex: { flex: 1 },
  bottomSpacer: { height: 40 },

  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#1f1f1f',
  },
  menuBtn: { width: 34, height: 34, justifyContent: 'center', alignItems: 'center' },
  menuLine: { width: 20, height: 1.5, backgroundColor: '#fff', marginVertical: 2.5, borderRadius: 1 },
  headerCenter: { flexDirection: 'row', alignItems: 'center' },
  statusDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#22c55e', marginRight: 10 },
  headerTitle: { color: '#fff', fontSize: 18, fontWeight: '600', letterSpacing: 4 },
  serverBadge: { color: '#888', fontSize: 12, marginLeft: 6, fontWeight: '500' },
  newChatBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#1a1a1a', justifyContent: 'center', alignItems: 'center' },
  newChatText: { color: '#fff', fontSize: 20, fontWeight: '300', marginTop: -2 },

  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 30, paddingBottom: 60 },
  emptyTitle: { color: '#fff', fontSize: 28, fontWeight: '600', marginBottom: 8 },
  emptySubtitle: { color: '#888', fontSize: 16, marginBottom: 40 },
  suggestions: { width: '100%' },
  suggestionChip: {
    backgroundColor: '#0f0f0f',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#222',
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderRadius: 14,
    marginBottom: 8,
  },
  suggestionText: { color: '#e5e5e5', fontSize: 15 },

  messagesContent: { padding: 16, paddingBottom: 12 },
  messageRow: { flexDirection: 'row', marginBottom: 14, alignItems: 'flex-end' },
  userRow: { justifyContent: 'flex-end' },
  assistantRow: { justifyContent: 'flex-start' },
  avatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#1f1f1f', justifyContent: 'center', alignItems: 'center', marginRight: 8, marginBottom: 2 },
  avatarText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  bubble: { maxWidth: '78%', paddingHorizontal: 15, paddingVertical: 10, borderRadius: 20 },
  userBubble: { backgroundColor: '#fff', borderBottomRightRadius: 6 },
  assistantBubble: { backgroundColor: '#1a1a1a', borderBottomLeftRadius: 6 },
  userText: { color: '#000', fontSize: 15, lineHeight: 21 },
  assistantText: { color: '#f5f5f5', fontSize: 15, lineHeight: 21 },

  inputWrapper: {
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#1f1f1f',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: '#111',
    borderRadius: 24,
    paddingLeft: 18,
    paddingRight: 6,
    paddingVertical: 6,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#222',
  },
  input: { flex: 1, color: '#fff', fontSize: 15, paddingVertical: 8, maxHeight: 120, lineHeight: 20 },
  sendBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#fff', justifyContent: 'center', alignItems: 'center', marginLeft: 8 },
  sendBtnDisabled: { backgroundColor: '#2a2a2a' },
  sendArrow: { color: '#000', fontSize: 18, fontWeight: '700', marginTop: -1 },

  // Drawer (Modal)
  drawerRoot: { flex: 1, flexDirection: 'row', backgroundColor: 'rgba(0,0,0,0.55)' },
  drawerPanel: {
    width: '82%',
    backgroundColor: '#0a0a0a',
    borderRightWidth: StyleSheet.hairlineWidth,
    borderRightColor: '#1f1f1f',
  },
  drawerDismiss: { flex: 1 },
  drawerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#1f1f1f',
  },
  drawerLogo: { color: '#fff', fontSize: 20, fontWeight: '600', letterSpacing: 4 },
  closeBtn: { width: 30, height: 30, borderRadius: 15, justifyContent: 'center', alignItems: 'center', backgroundColor: '#1a1a1a' },
  closeText: { color: '#fff', fontSize: 14 },

  newChatRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    marginHorizontal: 8,
    marginTop: 10,
    borderRadius: 12,
    backgroundColor: '#141414',
  },
  newChatIcon: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#1f1f1f', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  newChatIconText: { color: '#fff', fontSize: 18, marginTop: -2 },
  newChatRowText: { color: '#fff', fontSize: 15, fontWeight: '500' },

  sectionLabel: {
    color: '#666',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1.5,
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 10,
    textTransform: 'uppercase',
  },
  conversationsList: { flex: 1, paddingHorizontal: 8 },
  conversationItem: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 10, marginBottom: 2 },
  activeConversation: { backgroundColor: '#141414' },
  conversationMain: { flex: 1, paddingVertical: 8, paddingHorizontal: 6 },
  conversationPreview: { color: '#e0e0e0', fontSize: 14, marginBottom: 2 },
  conversationDate: { color: '#555', fontSize: 11 },
  deleteBtn: { width: 30, height: 30, justifyContent: 'center', alignItems: 'center' },
  deleteBtnText: { color: '#555', fontSize: 20, fontWeight: '300' },
  emptyConvos: { color: '#555', fontSize: 13, textAlign: 'center', paddingVertical: 30, fontStyle: 'italic' },

  drawerFooter: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#1f1f1f', paddingVertical: 10 },
  footerRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10 },
  userAvatar: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#fff', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  userAvatarText: { color: '#000', fontSize: 15, fontWeight: '700' },
  userInfo: { flex: 1 },
  userName: { color: '#fff', fontSize: 15, fontWeight: '600' },
  userStatus: { color: '#22c55e', fontSize: 11, marginTop: 1 },
  settingsIcon: { color: '#888', fontSize: 18 },

  // Settings
  settingsContainer: { flex: 1, backgroundColor: '#000' },
  settingsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#1f1f1f',
  },
  settingsTitle: { color: '#fff', fontSize: 22, fontWeight: '700' },
  settingsContent: { flex: 1, paddingHorizontal: 16 },
  settingsSection: {
    color: '#666',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginTop: 22,
    marginBottom: 10,
    paddingHorizontal: 4,
  },
  settingsCard: { backgroundColor: '#0f0f0f', borderRadius: 14, padding: 16, borderWidth: StyleSheet.hairlineWidth, borderColor: '#222' },

  serverCard: { backgroundColor: '#0f0f0f', borderRadius: 14, padding: 16, borderWidth: StyleSheet.hairlineWidth, borderColor: '#222', marginBottom: 8 },
  serverCardActive: { borderColor: '#22c55e', backgroundColor: '#0f1a0f' },
  serverCardHeader: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 6 },
  serverNameRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  serverName: { color: '#fff', fontSize: 17, fontWeight: '600', marginRight: 8 },
  serverStatusDot: { width: 8, height: 8, borderRadius: 4 },
  serverLabel: { color: '#22c55e', fontSize: 12, fontWeight: '500', marginBottom: 4 },
  serverDesc: { color: '#888', fontSize: 13, marginBottom: 4 },
  serverUrl: { color: '#555', fontSize: 11, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  activeBadge: { backgroundColor: '#22c55e', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  activeBadgeText: { color: '#000', fontSize: 10, fontWeight: '700' },

  settingsLabel: { color: '#aaa', fontSize: 14 },
  settingsInput: {
    backgroundColor: '#1a1a1a',
    color: '#fff',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    marginTop: 8,
    marginBottom: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#2a2a2a',
  },
  btnRow: { flexDirection: 'row' },
  btnHalf: { flex: 1 },
  btnHalfLeft: { flex: 1, marginRight: 8 },
  saveBtn: { backgroundColor: '#fff', borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  saveBtnText: { color: '#000', fontSize: 14, fontWeight: '600' },
  clearBtn: { backgroundColor: '#1a1a1a', borderRadius: 10, paddingVertical: 12, alignItems: 'center', borderWidth: StyleSheet.hairlineWidth, borderColor: '#2a2a2a' },
  clearBtnText: { color: '#aaa', fontSize: 14, fontWeight: '600' },

  divider: { height: StyleSheet.hairlineWidth, backgroundColor: '#222', marginVertical: 10 },

  accountRow: { flexDirection: 'row', alignItems: 'center' },
  userAvatarLarge: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#fff', justifyContent: 'center', alignItems: 'center', marginRight: 14 },
  userAvatarLargeText: { color: '#000', fontSize: 18, fontWeight: '700' },
  accountName: { color: '#fff', fontSize: 16, fontWeight: '600' },
  accountSub: { color: '#888', fontSize: 12, marginTop: 2 },

  dangerBtn: { backgroundColor: '#1a0808', borderWidth: StyleSheet.hairlineWidth, borderColor: '#ef4444', borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  dangerBtnText: { color: '#ef4444', fontSize: 14, fontWeight: '600' },
  dangerHint: { color: '#666', fontSize: 12, marginTop: 8, textAlign: 'center' },

  aboutRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 4 },
  aboutValue: { color: '#fff', fontSize: 14 },
});
