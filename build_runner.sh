#!/bin/bash
echo "Building ArgusRunnerBinary..."

SOURCES=$(find ArgusRunner -name "*.swift")

# Exclude legacy/unused files via grep
# We use a temporary file or chained greps for clarity
EXCLUDED_SOURCES=$(echo "$SOURCES" | \
grep -v "/Views/" | \
grep -v "/ViewModels/" | \
grep -v "/Stores/" | \
grep -v "/Tests/" | \
grep -v "/DataProviders/" | \
grep -v "View.swift" | \
grep -v "App.swift" | \
grep -v "Color+Hex.swift" | \
grep -v "Haptics.swift" | \
grep -v "Theme.swift" | \
grep -v "NotificationDelegate.swift" | \
grep -v "Heimdall" | \
grep -v "Orion" | \
grep -v "Atlas" | \
grep -v "Hermes" | \
grep -v "Agora" | \
grep -v "ChartDrawingModel.swift" | \
grep -v "PoseidonModels.swift" | \
grep -v "ReportScheduler.swift" | \
grep -v "FundDataManager.swift" | \
grep -v "ExpectationsStore.swift" | \
grep -v "Chiron" | \
grep -v "MacroRegimeService.swift" | \
grep -v "ArgusDecisionModels.swift" | \
grep -v "ArgusJournalModels.swift" | \
grep -v "ArgusNotificationModels.swift" | \
grep -v "ArgusLabModels.swift" | \
grep -v "ScoutStory.swift" | \
grep -v "DataHealth.swift" | \
grep -v "TradeLog.swift" | \
grep -v "MimirIssueDetector.swift" | \
grep -v "MimirModule" | \
grep -v "ReportEngine.swift" | \
grep -v "NotificationStore.swift" | \
grep -v "FundamentalScoreStore.swift" | \
grep -v "ServiceContainer.swift" | \
grep -v "DIContainer.swift" | \
grep -v "/Cache/" | \
grep -v "BacktestModels.swift" | \
grep -v "ChronosModels.swift" | \
grep -v "AuditLogService.swift" | \
grep -v "ArgusGrandCouncil.swift" | \
grep -v "PositionPlanModels.swift" | \
grep -v "EntrySnapshot.swift" | \
grep -v "AetherCouncilProtocol.swift" | \
grep -v "AetherCouncilMembers.swift" | \
grep -v "AetherCouncil.swift" | \
grep -v "SirkiyeEngine.swift" | \
grep -v "DecisionStrategy.swift" | \
grep -v "ArgusLabEngine.swift" | \
grep -v "ArgusBacktestEngine.swift" | \
grep -v "AISignalService.swift" | \
grep -v "AutoPilot" | \
grep -v "AlphaVantageService.swift" | \
grep -v "BorsaPyProvider.swift" | \
grep -v "EODHDProvider.swift" | \
grep -v "FMPProvider.swift" | \
grep -v "FinnhubSentimentProvider.swift" | \
grep -v "FinnhubService.swift" | \
grep -v "FundamentalsProvider.swift" | \
grep -v "TwelveDataFundamentalsProvider.swift" | \
grep -v "TwelveDataService.swift" | \
grep -v "YahooAuthenticationService.swift" | \
grep -v "YahooCandleAdapter.swift" | \
grep -v "YahooChartURLBuilder.swift" | \
grep -v "YahooFinanceProvider.swift" | \
grep -v "YahooAdapter.swift" | \
grep -v "ArgusScoutService.swift" | \
grep -v "PoseidonService.swift" | \
grep -v "PhoenixScannerService.swift" | \
grep -v "ChronosService.swift" | \
grep -v "ArgusVoiceService.swift" | \
grep -v "ArgusSpeechService.swift" | \
grep -v "NotificationManager.swift" | \
grep -v "ArgusShieldEngine.swift" | \
grep -v "AlertManager.swift" | \
grep -v "ClosedPlanStore.swift" | \
grep -v "OrionV2TuningStore.swift" | \
grep -v "OrionAnalysisService.swift" | \
grep -v "PositionPlanStore.swift" | \
grep -v "PositionDeltaTracker.swift" | \
grep -v "ComponentPerformanceService.swift" | \
grep -v "BISTBilancoEngine.swift" | \
grep -v "ChimeraSynergyEngine.swift" | \
grep -v "LiquidMotionManager.swift" | \
grep -v "InstrumentResolverVerifier.swift" | \
grep -v "HapticManager.swift" | \
grep -v "ArgusDataService.swift" | \
grep -v "ArgusDecisionEngine.swift" | \
grep -v "MarketDataProvider.swift" | \
grep -v "TradeBrainExecutor.swift" | \
grep -v "NewsServices.swift" | \
grep -v "YahooFinanceNewsProvider.swift" | \
grep -v "RSSNewsProvider.swift" | \
grep -v "BISTSentimentEngine.swift" | \
grep -v "BISTSentimentAdapter.swift" | \
grep -v "ArgusExplanationService.swift" | \
grep -v "EODHDProviderAdapter.swift" | \
grep -v "ArgusStorage.swift" | \
grep -v "PhoenixScenarioEngine.swift" | \
grep -v "ArgusLabStore.swift" | \
grep -v "ProviderAdapterRegistry.swift" | \
grep -v "ProviderCapabilityRegistry.swift" | \
grep -v "StrategyModels.swift" | \
grep -v "Models.swift" | \
grep -v "ChartDataModel.swift" | \
grep -v "CoinGeckoProvider.swift" | \
grep -v "MarketAnalysisService.swift" | \
grep -v "AnalysisService.swift" | \
grep -v "IndicatorService.swift" | \
grep -v "TechnicalAnalysisEngine.swift" | \
grep -v "ServiceProtocols.swift" | \
grep -v "TradeBrainConductor.swift" | \
grep -v "RiskMetricsEngine.swift" | \
grep -v "Council" | \
grep -v "MasterEngine" | \
grep -v "TimeSeriesModelService.swift" | \
grep -v "ArgusInboxService.swift" | \
grep -v "APIService.swift" | \
grep -v "MarketDataAdapter.swift" | \
grep -v "DataProviderProtocol.swift" | \
grep -v "ArgusVoice" | \
grep -v "ArgusFeedbackLoopService.swift" | \
grep -v "Demeter" | \
grep -v "Chiron" | \
grep -v "Heimdall" | \
grep -v "Orion" | \
grep -v "Atlas" | \

grep -v "Hermes" | \
grep -v "Agora" | \
grep -v "Poseidon" | \
grep -v "Athena" | \
grep -v "OverreactionEngine.swift" | \
grep -v "DataCacheService.swift" | \
grep -v "Alkindus" | \
grep -v "ArgusExecutionCore.swift" | \
grep -v "PortfolioRiskManager.swift" | \
grep -v "Phoenix" | \
grep -v "ArgusScoutService.swift" | \
grep -v "GeminiNewsService" | \
grep -v "LiquidityEngine" | \
grep -v "FieldBasedFallbackManager.swift" | \
grep -v "YahooFallbackProvider.swift" | \
grep -v "FundamentalScoreEngine.swift" | \
grep -v "SafeUniverseService.swift" | \
grep -v "TCMBDataService.swift" | \
grep -v "DataLayer" | \
grep -v "ArgusEtfEngine.swift" | \
grep -v "Titan" | \
grep -v "SmartPlanGenerator.swift" | \
grep -v "ForwardTest" | \
grep -v "Prometheus" | \
grep -v "ArgusCorseEngine.swift" | \
grep -v "ArgusPulseEngine.swift" | \
grep -v "ArgusEventBus.swift" | \
grep -v "EconomicCalendarService.swift" | \
grep -v "VortexEngine.swift" | \
grep -v "VortexEngine.swift" | \
grep -v "Bist" \
)

swiftc -o ArgusRunnerBinary $EXCLUDED_SOURCES

if [ $? -eq 0 ]; then
    echo "✅ Build success!"
    echo "Run with: ./ArgusRunnerBinary --symbol BTCUSDT --tf 15m --start-balance 30.0 --loop 0"
else
    echo "❌ Build failed."
    exit 1
fi
