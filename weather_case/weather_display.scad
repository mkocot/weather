include <nodemcu.scad>

hole_height = 12;
hole_width = 8.5;
totalheight = 13.7;
s = [65.7, 65.7, 3.9];
s2 = [60.6, 60.6, totalheight - s.z];
border = 2;
offset = 1.6;

module hole() {
    union() {
    margin_top = 1.6;
    hole_depth = 1.8;
    top_inlet = 0.7;
    xxx_size = 5;
    yyy_size = 1;
    side_inlet = 0.5;
    // hole H
    color("red")
    // this "height" dosn't matter
    cube([side_inlet, hole_width, 10]);
    translate([side_inlet, 0, 0]) {
    cube([hole_height, hole_width, top_inlet]);
    first_slope_size = 0.3;
    // first slope
    color("blue")
    translate([xxx_size+first_slope_size, 0, top_inlet])
        rotate([-90, 180, 0]) {
            points = [[0,0],[0, hole_depth - top_inlet],
            [first_slope_size, 0]];
            linear_extrude(hole_width)
            polygon(points);
        }
    //cube([first_slope_size, hole_width, hole_depth - top_inlet]);
       
    color("red")
    translate([xxx_size + first_slope_size, 0, top_inlet])
    cube([hole_height - xxx_size - yyy_size - first_slope_size, hole_width, hole_depth - top_inlet]);
        
    // now "slope"
    translate([hole_height - yyy_size, hole_width, top_inlet])
        rotate([90, 0, 0])
        color("magenta") {
            points = [
            [0, 0],
            [0, hole_depth - top_inlet],
            [yyy_size, 0],
            ];
            linear_extrude(hole_width)
            polygon(points);
        }
    }
}
    
}
module cap_original() {
    /*
    >      65.7       <
    +-----------------+ v
    |H               H|
    |                 | 
    |                 | 65.7
    |                 | 
    |H               H| 
    +-----------------+ ^
    

    -------------------V 3.9
    -+---------------+-^ 
     ||             ||
     ||             ||
    

    -------+ v    1.6
    -------+ ^v
    xx    y|    8.5
    xx    y|
    -------+  ^
    > 12   <
    
    xx = 5
    [empty] = 5.3
    yy = 1.5
    side inlet 0.5
    top inlet 0.7
    */

translate([0, 0, totalheight-s.z])
    difference()  
    {
 union() {
    cube(s);
    translate([-(s2.x  - s.x)/2, -(s2.y - s.y)/2, -s2.z])
    cube(s2);
 }
 
 pts = [
 [[0, 0, 0], [0, 0, 0]],
 [[0, 1, 0], [0, -s.y, 0]],
 [[1, 0, 0], [-s.x, 0, 0]],
 [[1, 0, 0], [-s.x, s.y-hole_height, 0]]
 ];
 for (i = [0:3]) {
 mirror(pts[i][0])
 translate(pts[i][1])
 union() {
    
    translate([-0.001, offset, s.z+0.001])
    mirror([0, 0, 1])
    hole();
     
    //translate([-0.001, s.x - hole_width - offset , s.z+0.001])
    //mirror([0, 0, 1])
    //hole();
 }
 }
 color("yellow")
   translate([-(s2.x- s.x)/2 + border, -(s2.y -s.y)/2 + border, -totalheight])
    cube([s2.x - border*2, s2.y-border*2, totalheight]);
 }

}

module cap_new() {
    border = 2;
    extend_by = 10;
    
    //difference()
    
  difference() {
    
    union() {
      cap_original();
      // extension
      color("purple")
      translate([(s.x-s2.x)/2 , offset + hole_width, totalheight])
      cube([s2.x, s2.y - hole_width*2+border, extend_by]);
    }
    color("blue")
    //cube([10, 10, totalheight]);
    // we want make it a slightly higher
    // and add "mount" slides for nodemcu
    translate([(s.x-s2.x)/2 + border, offset + hole_width + border, totalheight-border*2])
    cube([s2.x - border*2, s2.y - hole_width*2 - border, extend_by + border]);
  }

    // cutout center
    //translate([-(s2.x- s.x)/2 + border, -(s2.y -s.y)/2 + border, -0.001])
    //cube([s2.x - 2*border, s2.y - 2*border, extend_by + totalheight*2 - s.z]);
translate([
    (s.x - s2.x)/2 + nodemcu_bb_rot.x/2,
    offset + hole_width + border + ( nodemcu_board.z + border*2) + nodemcu_board.z + 0.4,
    totalheight + extend_by - 5 - border]) {
      difference() 
      {
        translate([-border, 0, 0])
        cube([nodemcu_board.y + border*2, nodemcu_board.z + border*2, 5 + 0.01]);
        
      color("red")
      translate([-0.3, (nodemcu_board.z + border*2)/2 - (    nodemcu_board.z + 1)/2 , -0.1])
      cube([nodemcu_board.y+0.6, nodemcu_board.z + 1, 40]);
        
      color("gray")
      translate([5, -10, -1])
      cube([nodemcu_board.y - 10, 50, 100]);
            color("gray")
translate([1, -10, 1])
cube([2, 30, 2]);
            color("gray")
translate([28, -10, 1])
cube([2, 30, 2]);
    }

}

}

nodemcu_bb_rot = [nodemcu_bb.y, nodemcu_bb.z, nodemcu_bb.x];

difference() {
union () {
cap_new();

//translate([nodemcu_bb.x, nodemcu_bb.y, 0]/2)
//translate([(s.x-s2.x)/2 + border, 0, 0])
// rotated so
// X = bb.y
// Y = bb.z
// Z = bb.x


if (0) {
// move closer to wall
    // 12 extend_by + border
    teh_size = 6;
translate([0, -10, -3])
translate([(s.x - s2.x)/2 + nodemcu_bb_rot.x/2, offset + hole_width + (s2.y - hole_width*2+border)/2 - nodemcu_bb_rot.y/2, -nodemcu_bb_rot.z + totalheight + 10])
translate([nodemcu_bb_rot.x, nodemcu_bb_rot.y, 0.01])
rotate([90, -90, 0]) {

     nodemcu();
    }
  }
}

// dziura na usb
translate([2, -4, 0])
translate([(s.x - s2.x)/2 + nodemcu_bb_rot.x/2, offset + hole_width + (s2.y - hole_width*2+border)/2 - nodemcu_bb_rot.y/2, -nodemcu_bb_rot.z + totalheight + 10])
translate([nodemcu_bb_rot.x, nodemcu_bb_rot.y, 0])
rotate([90, -90, 0])
translate([nodemcu_board.x - (nodemcu_board.x - pins.x)/2,
nodemcu_bb.y/2 -5,
nodemcu_bb.z - cpu.z])
cube([100, 15, 13]);
}

if (1) {
// add fillers to prevent generating support
// 0.5 - inlet
// 1 - 2*inlet
translate([hole_height+0.5, 0, totalheight])
{
  difference() 
  {
      color("red")
cube([s.x - hole_height*2+1, 12, 10]);
    translate([-6, -8.4, -8.6])
rotate([45, 0, 0])
cube(100);
  }
  

translate([0, s.y - 12, 0]) {
  difference() 
  {
    color("pink")
cube([s.x - hole_height*2+1, 12, 10]);
  translate([-6, 12, 0])
rotate([45, 0, 0])
cube(100);
  }
}
}
}