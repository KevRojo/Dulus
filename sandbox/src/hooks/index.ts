// ============================================================
// Dulus Hooks — Barrel exports
// ============================================================

export { useDulusHealth } from './useDulusHealth';
export type { ConnectionState, UseDulusHealthReturn } from './useDulusHealth';

export { useDulusChat } from './useDulusChat';
export type { UseDulusChatReturn } from './useDulusChat';

export { useDulusMemory } from './useDulusMemory';
export type { UseDulusMemoryReturn } from './useDulusMemory';

export { useDulusTasks } from './useDulusTasks';
export type { UseDulusTasksReturn } from './useDulusTasks';

export { useDulusSkills } from './useDulusSkills';
export type { UseDulusSkillsReturn } from './useDulusSkills';

export { useDulusAgents } from './useDulusAgents';
export type { UseDulusAgentsReturn } from './useDulusAgents';

export { useDulusEvents } from './useDulusEvents';

// Legacy hooks
export { useFileSystem } from './useFileSystem';
export { useOS, useWindows, useNotifications } from './useOSStore';
