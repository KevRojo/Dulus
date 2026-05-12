// ============================================================
// App Router — Maps appId to component
// ============================================================

import NotImplemented from '@/components/NotImplemented';
import FileManager from './FileManager';
import Terminal from './Terminal';
import Calculator from './Calculator';
import TextEditor from './TextEditor';
import Settings from './Settings';
import SystemMonitor from './SystemMonitor';
import Calendar from './Calendar';
import Notes from './Notes';
import Todo from './Todo';
import Clock from './Clock';
import Spreadsheet from './Spreadsheet';
import ArchiveManager from './ArchiveManager';
import Browser from './Browser';
import Email from './Email';
import Chat from './Chat';
import Weather from './Weather';
import MusicPlayer from './MusicPlayer';
import VideoPlayer from './VideoPlayer';
import ImageViewer from './ImageViewer';
import PhotoEditor from './PhotoEditor';
import VoiceRecorder from './VoiceRecorder';
import ScreenRecorder from './ScreenRecorder';
import Minesweeper from './Minesweeper';
import Snake from './Snake';
import Tetris from './Tetris';
import TicTacToe from './TicTacToe';
import Game2048 from './Game2048';
import Sudoku from './Sudoku';
import Chess from './Chess';
import Memory from './Memory';
import Pong from './Pong';
import Solitaire from './Solitaire';
import CodeEditor from './CodeEditor';
import JsonFormatter from './JsonFormatter';
import RegexTester from './RegexTester';
import MarkdownPreview from './MarkdownPreview';
import GitClient from './GitClient';
import ApiTester from './ApiTester';
import Base64Tool from './Base64Tool';
import ColorPalette from './ColorPalette';
import Drawing from './Drawing';
import ColorPicker from './ColorPicker';
import ImageGallery from './ImageGallery';
import AsciiArt from './AsciiArt';
import DocumentViewer from './DocumentViewer';
import Reminders from './Reminders';
import Contacts from './Contacts';
import PasswordManager from './PasswordManager';
import Whiteboard from './Whiteboard';
import RssReader from './RssReader';
import FtpClient from './FtpClient';
import NetworkTools from './NetworkTools';
import MediaConverter from './MediaConverter';
import FlappyBird from './FlappyBird';
import MatrixRain from './MatrixRain';
import TaskManager from './TaskManager';
import MemoryManager from './MemoryManager';
import AgentMonitor from './AgentMonitor';
import SkillsLauncher from './SkillsLauncher';
import type { FC } from 'react';

interface AppRouterProps {
  appId: string;
  windowId: string;
}

const AppRouter: FC<AppRouterProps> = ({ appId }) => {
  switch (appId) {
    case 'filemanager':
      return <FileManager />;
    case 'terminal':
      return <Terminal />;
    case 'calculator':
      return <Calculator />;
    case 'texteditor':
      return <TextEditor />;
    case 'settings':
      return <Settings />;
    case 'systemmonitor':
      return <SystemMonitor />;
    case 'calendar':
      return <Calendar />;
    case 'notes':
      return <Notes />;
    case 'todo':
      return <Todo />;
    case 'clock':
      return <Clock />;
    case 'spreadsheet':
      return <Spreadsheet />;
    case 'archivemanager':
      return <ArchiveManager />;
    case 'browser':
      return <Browser />;
    case 'email':
      return <Email />;
    case 'chat':
      return <Chat />;
    case 'weather':
      return <Weather />;
    case 'musicplayer':
      return <MusicPlayer />;
    case 'videoplayer':
      return <VideoPlayer />;
    case 'imageviewer':
      return <ImageViewer />;
    case 'photoeditor':
      return <PhotoEditor />;
    case 'voicerecorder':
      return <VoiceRecorder />;
    case 'screenrecorder':
      return <ScreenRecorder />;
    case 'minesweeper':
      return <Minesweeper />;
    case 'snake':
      return <Snake />;
    case 'tetris':
      return <Tetris />;
    case 'tictactoe':
      return <TicTacToe />;
    case 'game2048':
      return <Game2048 />;
    case 'sudoku':
      return <Sudoku />;
    case 'chess':
      return <Chess />;
    case 'memory':
      return <Memory />;
    case 'pong':
      return <Pong />;
    case 'solitaire':
      return <Solitaire />;
    case 'codeeditor':
      return <CodeEditor />;
    case 'jsonformatter':
      return <JsonFormatter />;
    case 'regextester':
      return <RegexTester />;
    case 'markdownpreview':
      return <MarkdownPreview />;
    case 'gitclient':
      return <GitClient />;
    case 'apitester':
      return <ApiTester />;
    case 'base64tool':
      return <Base64Tool />;
    case 'colorpalette':
      return <ColorPalette />;
    case 'drawing':
      return <Drawing />;
    case 'colorpicker':
      return <ColorPicker />;
    case 'imagegallery':
      return <ImageGallery />;
    case 'asciiart':
      return <AsciiArt />;
    case 'documentviewer':
      return <DocumentViewer />;
    case 'reminders':
      return <Reminders />;
    case 'contacts':
      return <Contacts />;
    case 'passwordmanager':
      return <PasswordManager />;
    case 'whiteboard':
      return <Whiteboard />;
    case 'rssreader':
      return <RssReader />;
    case 'ftpclient':
      return <FtpClient />;
    case 'networktools':
      return <NetworkTools />;
    case 'mediaconverter':
      return <MediaConverter />;
    case 'flappybird':
      return <FlappyBird />;
    case 'matrixrain':
      return <MatrixRain />;
    case 'taskmanager':
      return <TaskManager />;
    case 'memorymanager':
      return <MemoryManager />;
    case 'agentmonitor':
      return <AgentMonitor />;
    case 'skillslauncher':
      return <SkillsLauncher />;
    default:
      return <NotImplemented appId={appId} />;
  }
};

export default AppRouter;
