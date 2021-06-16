// fake nodemcu
// pins + cpu = 13mm
// borad
nodemcu_board = [57, 31.1, 1.6]; //
pins = [38, 2.5, 8.2];
cpu = [24, 16, 9 - nodemcu_board.z];
nodemcu_bb = nodemcu_board + [0, 0, cpu.z + pins.z];
module nodemcu() {
    translate([0, 0, pins.z + nodemcu_board.z])
    mirror([0, 0, 1]) {
    // board
    cube(nodemcu_board);
    translate([0, 0, nodemcu_board.z]) {
    // fake pins row
    color("black")
        translate([(nodemcu_board.x - pins.x)/2, 0, 0])
    cube(pins);
    // fake holes
    color("black")
        translate([(nodemcu_board.x - pins.x)/2, nodemcu_board.y - pins.y, 0])
    cube(pins);
    }
    // fake cpu
    color("red")
    translate([0, (nodemcu_board.y - cpu.y)/2, - cpu.z])
    cube(cpu);
}
}
module nodemcu_simple() {
    color("pink", 0.4)
    cube(nodemcu_bb);
}
//nodemcu();
//nodemcu_simple();