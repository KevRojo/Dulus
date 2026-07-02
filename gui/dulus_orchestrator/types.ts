export type ViewMode = 'chat' | 'core' | 'roundtable' | 'agents' | 'tasks' | 'brainstorm' | 'voice' | 'vision';

export type MessageBlock =
  | { kind: 'text'; text: string }
  | { kind: 'thinking'; text: string }
  | { kind: 'tool'; toolId: string; name: string; args?: any; result?: string; status: 'running' | 'done'; permitted?: boolean }
  | { kind: 'permission'; permId: string; description: string; answered?: boolean; granted?: boolean }
  | { kind: 'question'; questionId: string; question: string; options: Array<string | GuiQuestionOption>; allowFreetext: boolean; answer?: string };

export interface TurnStats {
  in?: number;
  out?: number;
  cacheRead?: number;
  cacheWrite?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'model' | 'system' | 'agent';
  text: string;
  blocks?: MessageBlock[];
  stats?: TurnStats;
  imageUrl?: string;
  isStreaming?: boolean;
  agentName?: string;
  toolCalls?: ToolCall[];
}

export interface WebchatSession {
  id: string;
  title: string;
  saved_at?: string;
  messages?: Array<{
    role: 'user' | 'assistant' | 'system' | string;
    content: string | Array<{ type?: string; text?: string }>;
  }>;
}

export interface ToolCall {
  id: string;
  name: string;
  args: any;
  result?: string;
  status: 'pending' | 'success' | 'error';
}

export interface SubAgent {
  id: string;
  type: 'coder' | 'reviewer' | 'researcher' | 'tester';
  task: string;
  status: 'idle' | 'working' | 'done' | 'error';
  branch: string;
}

export interface Persona {
  id: string;
  name: string;
  role: string;
  avatar: string;
  currentArgument?: string;
}

export interface Plugin {
  id: string;
  name: string;
  source: string;
  enabled: boolean;
  type: 'mcp' | 'native';
  profile?: string;
}

export interface Skill {
  id: string;
  name: string;
  source: string;
  enabled: boolean;
  profile?: string;
}

export interface ContextItem {
  id: string;
  name: string;
  kind: 'file' | 'text';
  source?: string;
  text?: string;
}

export interface RuntimeState {
  workspace: string;
  workspaces: string[];
  profile: string;
  profiles: string[];
  model: string;
  modelProvider?: string;
  models: string[];
  modelProviders?: Record<string, string>;
  permissionMode?: AppState['permissionMode'];
  plugins: Record<string, Plugin[]>;
  skills: Record<string, Skill[]>;
  contextItems: ContextItem[];
  webchatUrl: string;
}

export interface GuiQuestionOption {
  label: string;
  description?: string;
}

export interface GuiQuestion {
  id: string;
  question: string;
  options: GuiQuestionOption[];
  allow_freetext: boolean;
}

export interface Checkpoint {
  id: string;
  timestamp: number;
  description: string;
  turn: number;
}

export interface AppState {
  currentView: ViewMode;
  model: string;
  modelProvider?: string;
  models: string[];
  modelProviders: Record<string, string>;
  workspace: string;
  workspaces: string[];
  profile: string;
  profiles: string[];
  permissionMode: 'auto' | 'accept-all' | 'manual' | 'plan';
  isSSJMode: boolean;
  rightPanelOpen: boolean;
  pluginsByProfile: Record<string, Plugin[]>;
  skillsByProfile: Record<string, Skill[]>;
  contextItems: ContextItem[];
  webchatUrl?: string;
}

declare global {
  interface Window {
    __DULUS_RUNTIME__?: RuntimeState | null;
    pywebview?: {
      api?: {
        get_pending_question?: () => Promise<GuiQuestion | null>;
        answer_question?: (questionId: string, answer: string) => Promise<{ ok: boolean }>;
        submit_core_intake?: (
          topic: string,
          prompt: string,
          workspace: string,
          profile: string,
          model: string,
        ) => Promise<{ ok: boolean; prompt?: string }>;
        get_webchat_sessions?: (webchatUrl?: string) => Promise<WebchatSession[]>;
        send_gui_message?: (message: string) => Promise<Array<Record<string, any>>>;
        send_webchat_message?: (message: string, webchatUrl?: string) => Promise<Array<Record<string, any>>>;
        open_pet_window?: () => Promise<{ ok: boolean; pid?: number; message?: string }>;
        set_plugin_enabled?: (
          profile: string,
          pluginId: string,
          enabled: boolean,
        ) => Promise<{ ok: boolean; profile: string; plugin: string; enabled: boolean }>;
      };
    };
  }
}

