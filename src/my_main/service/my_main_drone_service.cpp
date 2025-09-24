#include "service.hpp"
#include <iostream>
#include <thread>
#include <sstream>
#include <vector>
#include <string>
#include <queue>
#include <csignal>
#include "hakoniwa/ihakoniwa_drone_service.hpp"
#include "hakoniwa/hakoniwa_conductor.hpp"

using namespace hako::aircraft;
using namespace hako::controller;
using namespace hako::service;
using namespace hako::logger;
using namespace hako::config;
using namespace hako::drone;

static bool is_simulation_running = true;

void signal_handler(int signum) {
    std::cout << "Received signal: " << signum << ". Stopping simulation." << std::endl;
    is_simulation_running = false;
}

int main(int argc, const char* argv[]) {
    if (argc != 5) {
        std::cerr << "Usage: " << argv[0] << " <delta_time_usec> <max_delay_usec> <drone_config_dir_path> <asset_config_path>" << std::endl;
        return 1;
    }

    long long delta_time_usec = std::stoll(argv[1]);
    long long max_delay_usec = std::stoll(argv[2]);
    const char* drone_config_dir_path = argv[3];
    const char* asset_config_path = argv[4];

    IHakoLogger::enable();

    DroneConfigManager configManager;
    std::string drone_config_file_path = std::string(drone_config_dir_path) + "/drone_config_0.json";
    std::ifstream configFile(drone_config_file_path);
    if (!configFile.is_open()) {
        std::cerr << "Unable to open config file: " << drone_config_file_path << std::endl;
        return 1;
    }
    std::stringstream ss;
    ss << configFile.rdbuf();
    configManager.loadConfigFromText(ss.str());

    auto aircraft_container = IAirCraftContainer::create();
    aircraft_container->createAirCrafts(configManager);

    DroneConfig& config = configManager.getConfig(0);
    std::string controller_config_file_path = config.getControllerParamFilePath();
    std::ifstream controllerConfigFile(controller_config_file_path);
    if (!controllerConfigFile.is_open()) {
        std::cerr << "Unable to open controller config file: " << controller_config_file_path << std::endl;
        return 1;
    }
    std::stringstream controller_ss;
    controller_ss << controllerConfigFile.rdbuf();
    config.setControllerParamText(controller_ss.str());

    std::shared_ptr<IAircraftControllerContainer> controller_container = IAircraftControllerContainer::create();
    controller_container->createAircraftControllers(configManager, false); // keyboard control disabled

    std::shared_ptr<IDroneServiceContainer> service_container = IDroneServiceContainer::create(aircraft_container, controller_container);
  
    auto hako_service = hako::drone::IHakoniwaDroneService::create();
    if (!hako_service) {
        std::cerr << "Failed to create IHakoniwaDroneService" << std::endl;
        return 1;
    }
    std::cout << "DroneServiceContainer created" << std::endl;

    std::string asset_name = "drone";
    std::cout << "asset_name: " << asset_name << std::endl;
    std::string asset_config_path_str = asset_config_path;
    if (!hako_service->registerService(asset_name, asset_config_path_str, delta_time_usec, max_delay_usec, service_container)) {
        std::cerr << "Failed to register service" << std::endl;
        return 1;
    }
    std::cout << "HakoniwaDroneService::registerService() done" << std::endl;

    hako_service->startService();

    // if (!HakoniwaConductor::startService(delta_time_usec, max_delay_usec)) {
    //     std::cerr << "Failed to start HakoniwaConductor service" << std::endl;
    //     return 1;
    // }

    std::cout << "Hakoniwa service started. Waiting for simulation to end." << std::endl;

    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    while (is_simulation_running) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }

    // HakoniwaConductor::stopService();
    // std::cout << "Hakoniwa service stopped." << std::endl;

    return 0;
}